"use client";

import Graph3DCanvas from "@/components/graph3DCanvas";
import { ProverbsCard } from "@/components/proverbs";
import { WeatherCard } from "@/components/weather";
import { AgentState } from "@/lib/types";
import {
  useCoAgent,
  useFrontendTool,
  useRenderToolCall,
} from "@copilotkit/react-core";
import { CopilotKitCSSProperties, CopilotSidebar } from "@copilotkit/react-ui";
import { useState } from "react";

type NodeProperties = {
  role?: unknown;
  secondaryRole?: unknown;
  special?: unknown;
};

type GraphNodePayload = {
  id?: string | number;
  name?: string | number;
  label?: string | number;
  index?: string | number;
  group?: unknown;
  properties?: NodeProperties;
  labels?: string[];
};

type NodeDetails = {
  found?: boolean;
  name?: string;
  error?: string;
  labels?: string[];
  properties?: NodeProperties;
};

export default function CopilotKitPage() {
  const [themeColor, setThemeColor] = useState("#6366f1");

  // 🪁 Frontend Actions: https://docs.copilotkit.ai/adk/frontend-actions
  useFrontendTool({
    name: "setThemeColor",
    parameters: [
      {
        name: "themeColor",
        description: "The theme color to set. Make sure to pick nice colors.",
        required: true,
      },
    ],
    handler({ themeColor }) {
      setThemeColor(themeColor);
    },
  });

  return (
    <main
      style={
        { "--copilot-kit-primary-color": themeColor } as CopilotKitCSSProperties
      }
    >
      <CopilotSidebar
        disableSystemMessage={true}
        clickOutsideToClose={false}
        defaultOpen={true}
        labels={{
          title: "Popup Assistant",
          initial: "👋 Hi, there! You're chatting with an agent.",
        }}
        suggestions={[
          {
            title: "Generative UI",
            message: "Get the weather in San Francisco.",
          },
          {
            title: "Frontend Tools",
            message: "Set the theme to green.",
          },
          {
            title: "Write Agent State",
            message: "Add a proverb about AI.",
          },
          {
            title: "Update Agent State",
            message:
              "Please remove 1 random proverb from the list if there are any.",
          },
          {
            title: "Read Agent State",
            message: "What are the proverbs?",
          },
        ]}
      >
        <YourMainContent themeColor={themeColor} />
      </CopilotSidebar>
    </main>
  );
}

function YourMainContent({ themeColor }: { themeColor: string }) {
  const { state, setState } = useCoAgent<AgentState>({
    name: "my_agent",
    initialState: {
      proverbs: [
        "CopilotKit may be new, but its the best thing since sliced bread.",
      ],
    },
  });

  const [selectedSurvivor, setSelectedSurvivor] = useState<string[]>([]);
  const [nodeProps, setNodeProps] = useState<NodeDetails | null>(null);
  const [hoveredRole, setHoveredRole] = useState<string | null>(null);

  const roleColors: { label: string; color: string }[] = [
    { label: "First Responder", color: "#e74c3c" },
    { label: "Navigator", color: "#3498db" },
    { label: "Lookout", color: "#2ecc71" },
    { label: "Assistant", color: "#f39c12" },
    { label: "Default", color: "#ecf0f1" },
  ];

  useRenderToolCall(
    {
      name: "get_weather",
      description: "Get the weather for a given location.",
      parameters: [{ name: "location", type: "string", required: true }],
      render: ({ args }) => {
        return <WeatherCard location={args.location} themeColor={themeColor} />;
      },
    },
    [themeColor],
  );

  return (
    <div className="h-screen w-full bg-black text-white flex flex-row items-stretch">
      <div
        className="h-screen overflow-y-auto p-6 z-10 bg-black/75 border-r border-cyan-900/40 text-sm text-white backdrop-blur-sm"
        style={{ flex: "0 0 34%", maxWidth: "520px", minWidth: "300px" }}
      >
        <h1
          className="text-2xl font-bold uppercase tracking-[0.2em]"
          style={{
            lineHeight: 1,
            marginBottom: "20px",
            color: themeColor,
            textShadow: `0 0 8px ${themeColor}80`,
          }}
        >
          Survivor Network <span style={{ opacity: 0.7 }}>Node-Map</span>
        </h1>
        <p className="mt-2 text-xs uppercase tracking-wider text-gray-300">
          Role legend and node details
        </p>

        <div className="mt-4 rounded-lg border border-gray-800 bg-black/40 p-3 flex flex-col items-start gap-2">
          {roleColors.map((rc) => {
            const rl = rc.label.toLowerCase();
            const hoveredLower = hoveredRole?.toLowerCase() ?? null;
            const selectedRole = nodeProps?.properties?.role ?? null;
            const selectedLower = selectedRole?.toLowerCase() ?? null;
            const isActive = hoveredLower === rl || selectedLower === rl;

            return (
              <div
                key={rc.label}
                className="rounded-md px-2 py-1 bg-black/20 border border-gray-800 flex flex-row items-center gap-2 w-max"
              >
                <div
                  style={{
                    width: 14,
                    height: 14,
                    background: rc.color,
                    borderRadius: 3,
                    border: isActive ? "2px solid #fff" : "1px solid #333",
                    transform: isActive ? "scale(1.2)" : "scale(1)",
                  }}
                />
                <div className="text-xs text-gray-300 tracking-wide">{rc.label}</div>
              </div>
            );
          })}
        </div>

        <div className="mt-5 text-white/90">
          <div className="text-sm">
            <strong className="text-cyan-300">Selected:</strong>{" "}
            {selectedSurvivor[0] ?? "None"}
          </div>
          {nodeProps && (
            <div className="mt-2 max-w-full overflow-auto bg-black/50 border border-gray-800 p-3 rounded-lg shadow-lg shadow-black/30">
              {nodeProps.found === false ? (
                <div className="text-red-300">No properties found for {nodeProps.name}</div>
              ) : nodeProps.error ? (
                <div className="text-red-300">{nodeProps.error}</div>
              ) : (
                <div>
                  <div className="text-sm text-gray-300">
                    Labels: {(nodeProps.labels || []).join(", ")}
                  </div>
                  <ul className="mt-2 space-y-1 text-xs text-white/90">
                    {nodeProps.properties && (
                      <>
                        {"role" in nodeProps.properties && (
                          <li>
                            <strong>role:</strong> {String(nodeProps.properties.role)}
                          </li>
                        )}
                        {"secondaryRole" in nodeProps.properties && (
                          <li>
                            <strong>secondaryRole:</strong>{" "}
                            {String(nodeProps.properties.secondaryRole)}
                          </li>
                        )}
                        {"special" in nodeProps.properties && (
                          <li>
                            <strong>special:</strong> {String(nodeProps.properties.special)}
                          </li>
                        )}
                      </>
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="mt-6">
          <ProverbsCard state={state} setState={setState} />
        </div>
      </div>

      <div className="relative" style={{ flex: 1, minWidth: 0, height: "100%" }}>
        <Graph3DCanvas
          highlightNodes={selectedSurvivor}
          onNodeClick={async (node: unknown) => {
            if (!node || typeof node !== "object") return;
            const nodeData = node as GraphNodePayload;
            const id =
              nodeData.id ?? nodeData.name ?? nodeData.label ?? nodeData.index;
            if (id === undefined) return;

            const idStr = String(id);
            setSelectedSurvivor([idStr]);

            if (nodeData.properties || nodeData.labels) {
              setNodeProps({
                found: true,
                name: idStr,
                properties: nodeData.properties || {},
                labels: nodeData.labels || [],
              });
              return;
            }

            try {
              const resp = await fetch(
                `http://localhost:8000/api/node/${encodeURIComponent(idStr)}`,
              );

              if (!resp.ok) {
                setNodeProps({ error: `Server returned ${resp.status}` });
                return;
              }

              const data = await resp.json();
              setNodeProps(data);
            } catch (err) {
              setNodeProps({ error: String(err) });
            }
          }}
          onNodeHover={(node: unknown) => {
            if (!node || typeof node !== "object") {
              setHoveredRole(null);
              return;
            }
            const nodeData = node as GraphNodePayload;
            const role =
              nodeData.properties?.secondaryRole ??
              nodeData.properties?.role ??
              nodeData.group ??
              null;
            setHoveredRole(role ? String(role) : null);
          }}
        />
      </div>
    </div>
  );
}
