import sys
import json
import asyncio

from cluster import create_cluster
from layout import Layout
from recs import store_edges
from shows import (
    store_metadata,
    get_ids,
    process_metadata,
    store_anilist_metadata
)

MAL_METADATA_FILENAME = 'data/metadata.json'
ANILIST_METADATA_FILENAME = 'data/metadata-anilist.json'


async def main():
    # If reset flag, delete existing metadata and pull it again. Takes hours.
    if len(sys.argv) == 2 and sys.argv[1] == 'reset':
        ids = await get_ids()

        with open(MAL_METADATA_FILENAME, 'w') as f:
            json.dump({}, f)

        with open(ANILIST_METADATA_FILENAME, 'w') as f:
            json.dump({}, f)

        mal_task = asyncio.to_thread(store_metadata, ids)
        ani_task = asyncio.to_thread(store_anilist_metadata, ids)

        await asyncio.gather(mal_task, ani_task)

    # Load metadata
    with open(MAL_METADATA_FILENAME, 'r') as f:
        metadata_json = json.load(f)

    with open(ANILIST_METADATA_FILENAME, 'r') as f:
        anilist_metadata_json = json.load(f)

    metadata = process_metadata(metadata_json, anilist_metadata_json)

    # Get edges
    edges = store_edges(metadata)

    # Create clusters
    root_cluster = await create_cluster(edges)
    print("Finished clustering")

    # Layout clusters
    print("Starting layout")
    layout = Layout(root_cluster.to_node_dict(), edges, 20)

    while not layout.done:
        layout.tick()

    with open('data/layout.json', 'w') as f:
        json.dump(layout.to_json(), f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
