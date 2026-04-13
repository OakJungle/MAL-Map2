import * as _ from "lodash";
import { getTiers, params_dict } from "./base_utils";

export type ClusterJSON = {
    id: number,
    tier: number,
    nodes: number[],
    clusters: ClusterJSON[],
}

export class Cluster {
    id: number;
    tier: number;
    nodes: number[];
    clusters: Cluster[];

    constructor(id: number, tier: number, nodes: number[] = []) {
        this.id = id;
        this.tier = tier;
        this.nodes = nodes;
        this.clusters = [];
    }

    static fromJSON(json: ClusterJSON): Cluster {
        const cluster = new Cluster(json.id, json.tier, json.nodes);
        cluster.clusters = json.clusters.map(c => Cluster.fromJSON(c));
        return cluster;
    }

    toNodeDict(): { [key: string]: number[] } {
        let json: { [key: string]: number[] } = {};

        // leaf nodes
        for (let node of this.nodes) {
            json[node] = [node];
        }

        // merge child dictionaries
        for (let c of this.clusters) {
            Object.assign(json, c.toNodeDict());
        }

        // find max depth
        const max_len = Math.max(
            0,
            ...Object.values(json).map(arr => arr.length)
        );

        // pad paths with current cluster id
        for (let [id, path] of Object.entries(json)) {
            while (path.length <= max_len) {
                path.unshift(this.id);
            }
        }

        return json;
    }
}

export function currentLanguage() {
    return params_dict.language || "en";
}

export function nativeTitle(metadata: ANIME_DATA) {
    return currentLanguage() == 'en' ? metadata.englishTitle || metadata.title : metadata.title;
}


export async function queryUser(username: string): Promise<number[]> {
    const proxy_url = 'https://corsanywhere.herokuapp.com/';
    const mal_url = `https://api.myanimelist.net/v2/users/${username}/animelist`;
    const full_url = `${proxy_url}${mal_url}?` + new URLSearchParams({
        'limit': '1000',
        'status': 'completed',
        'sort': 'list_score',
    }).toString();
    const response = await fetch(full_url, {
        headers: {
            "X-MAL-CLIENT-ID": "e0e691a27a61d8cca4d3446774022c20", // please dont steal. This is used on the client, impossible to hide.
        },
    });
    try {
        const data = await response.json();
        const ids = data.data.map((entry: any) => entry.node.id);
        console.log(ids);
        return ids;
    } catch (e) {
        console.log(e);
        return null;
    }
}

function displayTitle(metadata: any) {
    let title = currentLanguage() == 'en' ?
        metadata.englishTitle ||
        metadata.title : metadata.title;
    // discard after colon
    const colon = title.indexOf(': ');
    if (colon !== -1) {
        title = title.slice(0, colon);
    }
    return title;
}
import Anime from "../../../data-collection/data/min_metadata.json";
import Clusters_ from "../../../data-collection/data/clusters.json";
import { ANIME_DATA } from "./types";
export const Metadata = _.mapValues(Anime, (metadata: any) => Object.assign(new ANIME_DATA(), metadata, {
    display_title: displayTitle(metadata),
}));
export const Clusters = Cluster.fromJSON(Clusters_);
export const Tier: { [id: number]: number } = getTiers(Clusters, Metadata);
export const Cluster_Nodes = Clusters.toNodeDict();