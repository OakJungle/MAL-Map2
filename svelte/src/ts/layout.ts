import { Edge } from "./edge";

type Positions = { [id: number]: { x: number, y: number, hue: number } };

export class Layout {
    nodes: { id: number; x: number; y: number; hue: number }[];
    edges: Edge[];

    constructor(
        nodes: { id: number; x: number; y: number; hue: number }[] = [],
        edges: Edge[] = []
    ) {
        this.nodes = nodes;
        this.edges = edges;
    }

    toJSON(): { nodes: Positions; edges: number[][] } {
        let positions: Positions = {};

        for (const node of this.nodes) {
            positions[node.id] = {
                x: node.x,
                y: node.y,
                hue: node.hue,
            };
        }

        let edges: number[][] = [];
        for (const edge of this.edges) {
            edges.push([edge.source.id, edge.target.id, edge.weight]);
        }

        return { nodes: positions, edges };
    }
}
