import json
import time
import os
import requests
from typing import Dict, List
from tqdm import tqdm

KEY = os.environ.get("MAL_KEY", "e0e691a27a61d8cca4d3446774022c20")


# -----------------------
# GET IDS
# -----------------------

import json
import os
import time
import requests
from typing import Dict, List
from tqdm import tqdm


def load_json(filename):
    if os.path.exists(filename):
        with open(filename) as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


def request_with_retry(method, url, *, headers=None, json_data=None, retries=3):
    for attempt in range(retries):
        res = requests.request(method, url, headers=headers, json=json_data)

        # ✅ Handle AniList rate limit (429)
        if res.status_code == 429:
            retry_after = int(res.headers.get("Retry-After", 60))
            print(f"Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        if not res.ok:
            print(f"HTTP {res.status_code}: retrying...")
            time.sleep(attempt + 1)
            continue

        return res.json()

    raise Exception("Request failed after retries")

async def get_ids():
    print("Getting ids from MAL")

    ids = []
    for i in range(10):
        url = f"https://api.myanimelist.net/v2/anime/ranking?ranking_type=bypopularity&limit=500&offset={i * 500}"
        data = request_with_retry("GET", url, headers={"X-MAL-CLIENT-ID": KEY})

        ids.extend(show["node"]["id"] for show in data.get("data", []))
        time.sleep(0.6)

    return list(set(ids))

async def store_anilist_metadata(ids: List[int], filename='data/metadata-anilist.json'):
    metadata = load_json(filename)

    print(f"{len(metadata)} shows already have anilist metadata out of {len(ids)}")

    for id in tqdm(ids):
        key = str(id)
        if key in metadata:
            continue

        metadata[key] = {}
        page = 1

        try:
            while True:
                query = {
                    "query": """
                    query ($id: Int, $i: Int) {
                        Media (id: $id, type: ANIME) {
                            recommendations(page: $i) {
                                nodes {
                                    mediaRecommendation { idMal }
                                    rating
                                }
                            }
                        }
                    }
                    """,
                    "variables": {"id": id, "i": page}
                }

                data = request_with_retry(
                    "POST",
                    "https://graphql.anilist.co",
                    json_data=query
                )

                nodes = data["data"]["Media"]["recommendations"]["nodes"]
                nodes = [
                    n for n in nodes
                    if n and n.get("mediaRecommendation") and n["mediaRecommendation"].get("idMal")
                ]

                if not nodes:
                    break

                for node in nodes:
                    if (node.get("rating") or 0) < 1:
                        continue

                    rec = str(node["mediaRecommendation"]["idMal"])
                    metadata[key][rec] = metadata[key].get(rec, 0) + node["rating"]

                page += 1
                time.sleep(0.7)  # ~85 req/min (safe under 90)

        except Exception as e:
            print("Error:", id, e)

        if len(metadata) % 20 == 0:
            save_json(filename, metadata)

    save_json(filename, metadata)
    return metadata

async def store_metadata(ids: List[int], filename='data/metadata.json'):
    metadata = load_json(filename)

    print(f"{len(metadata)} shows already have metadata out of {len(ids)}")

    for id in tqdm(ids):
        key = str(id)
        if key in metadata:
            continue

        try:
            params = "title,alternative_titles,num_list_users,media_type,start_season,nsfw,synopsis,score,genres,rank,popularity,main_picture,related_anime,mean,recommendations"
            url = f"https://api.myanimelist.net/v2/anime/{id}?fields={params}"

            metadata[key] = request_with_retry(
                "GET",
                url,
                headers={"X-MAL-CLIENT-ID": KEY}
            )

        except Exception as e:
            print("Failed:", id, e)
            metadata[key] = None

        time.sleep(0.8)

        if len(metadata) % 20 == 0:
            save_json(filename, metadata)

    save_json(filename, metadata)
    return metadata


# -----------------------
# PROCESSING
# -----------------------

def parse_metadata(json_data):
    return {
        "id": json_data.get("id"),
        "title": json_data.get("title"),
        "englishTitle": json_data.get("alternative_titles", {}).get("en"),
        "url": f"https://myanimelist.net/anime/{json_data.get('id')}",
        "picture": json_data.get("main_picture", {}).get("medium"),
        "synopsis": json_data.get("synopsis"),
        "type": json_data.get("media_type"),
        "score": json_data.get("mean"),
        "genres": [g["name"] for g in json_data.get("genres", [])],
        "ranked": json_data.get("rank"),
        "popularity": json_data.get("popularity"),
        "members": json_data.get("num_list_users"),
        "related": [
            {"id": r["node"]["id"], "relation_type": r["relation_type"]}
            for r in json_data.get("related_anime", [])
        ],
        "recommendations": [
            {"id": r["node"]["id"], "count": r["num_recommendations"]}
            for r in json_data.get("recommendations", [])
        ],
        "year": json_data.get("start_season", {}).get("year"),
        "nsfw": json_data.get("nsfw") not in ["white", "gray"],
    }


def augment_metadata(metadata, anilist_metadata):
    for id in anilist_metadata:
        if id not in metadata:
            continue

        for rec, count in anilist_metadata[id].items():
            rec = int(rec)
            found = next((r for r in metadata[id]["recommendations"] if r["id"] == rec), None)

            if found:
                found["count"] += count
            else:
                metadata[id]["recommendations"].append({"id": rec, "count": count})

    return metadata


def filter_metadata(metadata):
    filtered = {}

    for id, show in metadata.items():
        if show.get("score") and show.get("type") == "tv" and not show.get("nsfw"):
            filtered[id] = show

    keys = [id for id in filtered if filtered[id].get("popularity", 9999) < 4000]

    return {k: filtered[k] for k in keys}


def merge_seasons(data):
    data = {int(k): v for k, v in data.items()}

    def get_canonical(show_id):
        show = data[show_id]

        if not show.get("related"):
            return show_id

        related = [show_id]

        while True:
            new_related = []
            for id in related:
                if id not in data:
                    continue

                rels = [
                    r["id"]
                    for r in data[id].get("related", [])
                    if r["relation_type"] in ["sequel", "prequel"]
                ]
                new_related.extend(rels)
                new_related.append(id)

            new_related = list(set(r for r in new_related if r in data))

            if len(new_related) == len(related):
                break

            related = new_related

        related = [r for r in related if data[r].get("score")]

        if len(related) < 2:
            return show_id

        return min(related, key=lambda x: data[x].get("popularity", 9999))

    canonical_ids = {id: get_canonical(id) for id in data}

    # merge recs into canonical
    for id in data:
        cid = canonical_ids[id]
        if cid != id:
            recs = data[id]["recommendations"]
            data[cid]["recommendations"].extend(recs)

    merged = {}

    for id in data:
        cid = canonical_ids[id]
        if cid == id:
            grouped = {}

            for r in data[id]["recommendations"]:
                rid = canonical_ids.get(r["id"])
                if rid is None:
                    continue

                grouped[rid] = grouped.get(rid, 0) + r["count"]

            data[id]["recommendations"] = [
                {"id": k, "count": v} for k, v in grouped.items()
            ]

            merged[id] = data[id]

    return merged


def process_metadata(metadata, anilist_metadata):
    data = {k: parse_metadata(v) for k, v in metadata.items() if v}

    data = augment_metadata(data, anilist_metadata)
    print(f"{len(data)} shows have metadata")

    merged = merge_seasons(data)
    print(f"{len(merged)} shows after merging seasons")

    filtered = filter_metadata(merged)
    print(f"{len(filtered)} shows filtered")

    with open("data/min_metadata.json", "w") as f:
        json.dump(filtered, f, indent=2)

    return filtered
