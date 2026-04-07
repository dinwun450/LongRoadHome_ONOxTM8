"use client";

import axios from "axios";
import { AxiosResponse } from "axios";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), {
  ssr: false,
});

type Props = {
  highlightNodes?: string[];
  onNodeClick?: (node: unknown) => void;
  onNodeHover?: (node: unknown) => void;
};

type GraphData = {
  nodes: GraphNode[];
  links: GraphLink[];
  error?: string;
};

type GraphNode = {
  id?: string | number;
  group?: string;
  properties?: {
    role?: unknown;
    secondaryRole?: unknown;
    special?: unknown;
  };
  __obj?: THREE.Group;
};

type GraphLink = {
  source: string;
  target: string;
  label?: string;
};

const roleColorMap: Record<string, string> = {
  "first responder": "#e74c3c",
  navigator: "#3498db",
  lookout: "#2ecc71",
  assistant: "#f39c12",
};

const Graph3DCanvas = ({
  highlightNodes = [],
  onNodeClick,
  onNodeHover,
}: Props) => {
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    axios
      .get("http://localhost:8000/api/graph")
      .then((res: AxiosResponse<GraphData>) => {
        setData({ nodes: res.data.nodes || [], links: res.data.links || [] });
        if (res.data.error) {
          setApiError(res.data.error);
        }
      })
      .catch((err: unknown) => {
        console.error("Error loading graph:", err);
        setApiError("Could not load graph API at http://localhost:8000/api/graph");
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      if (entries.length > 0) {
        const { width, height } = entries[0].contentRect;
        setDimensions({ width, height });
      }
    });

    observer.observe(containerRef.current);

    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        background: "#080802",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <ForceGraph3D
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="#080802"
        graphData={data}
        nodeLabel="id"
        nodeAutoColorBy="group"
        nodeThreeObjectExtend={true}
        onNodeClick={(node: unknown) => onNodeClick && onNodeClick(node)}
        onNodeHover={(node: unknown) => onNodeHover && onNodeHover(node)}
        nodeThreeObject={(nodeObject: object) => {
          const node = nodeObject as GraphNode;
          const idStr = node?.id !== undefined ? String(node.id) : "";
          const isHighlighted = highlightNodes.some((h) => String(h) === idStr);

          const secRole = node?.properties?.secondaryRole ?? node?.properties?.role;
          const roleKey = String(secRole || "").trim().toLowerCase();
          const roleColor = roleColorMap[roleKey] ?? "#ecf0f1";
          const nodeColor = isHighlighted ? "#1abc9c" : roleColor;

          if (node.__obj) {
            const sphere = node.__obj.getObjectByName("sphere");
            if (sphere instanceof THREE.Mesh && sphere.material instanceof THREE.MeshBasicMaterial) {
              sphere.material.color.set(nodeColor);
              const scale = isHighlighted ? 1.8 : 1;
              sphere.scale.set(scale, scale, scale);
            }
            return node.__obj;
          }

          const geometry = new THREE.SphereGeometry(4, 16, 16);
          const material = new THREE.MeshBasicMaterial({ color: 0xffffff });
          const sphere = new THREE.Mesh(geometry, material);
          sphere.name = "sphere";
          sphere.castShadow = false;
          sphere.receiveShadow = false;

          const initialScale = isHighlighted ? 1.8 : 1;
          sphere.scale.set(initialScale, initialScale, initialScale);
          sphere.material.color.set(nodeColor);

          const group = new THREE.Group();
          group.add(sphere);
          node.__obj = group;
          return group;
        }}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
      />
      {(isLoading || apiError || data.nodes.length === 0) && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            color: "#e5e7eb",
            fontSize: "14px",
            textAlign: "center",
            padding: "24px",
            background: "linear-gradient(180deg, rgba(8,8,2,0.10), rgba(8,8,2,0.35))",
          }}
        >
          {isLoading
            ? "Loading graph..."
            : apiError
              ? `Graph unavailable: ${apiError}`
              : "No graph nodes returned by /api/graph"}
        </div>
      )}
    </div>
  );
};

export default Graph3DCanvas;
