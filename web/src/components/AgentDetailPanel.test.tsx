import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentDetailPanel } from "@/components/AgentDetailPanel";
import type { AgentPromptSettings, NexusTrace, TopologyNode } from "@/types/nexus-payload";

const node: TopologyNode = {
  id: "n6",
  actor: "strategy-planner",
  label: "Strategy Planner",
  status: "ACTIVE",
};

const traces: NexusTrace[] = [];

describe("AgentDetailPanel", () => {
  it("hydrates prompt inputs from promptDefaults", () => {
    const promptDefaults: AgentPromptSettings = {
      node_id: "n6",
      actor_id: "strategy-planner",
      model: "gpt-4.1",
      temperature: 0.15,
      max_tokens: 4096,
      tools: ["mcp.strategy.grid", "mcp.inventory.read"],
      system_prompt: "You are Strategy Planner.",
      task_prompt: "Given scorecard, propose next action.",
      cot_enabled: true,
    };

    render(
      <div style={{ height: 800 }}>
        <AgentDetailPanel nodeId="n6" node={node} traces={traces} promptDefaults={promptDefaults} />
      </div>,
    );

    expect(screen.getByText("Prompt configuration")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("System prompt for this agent…")).toHaveValue(
      "You are Strategy Planner.",
    );
    expect(screen.getByPlaceholderText("Task / instruction template…")).toHaveValue(
      "Given scorecard, propose next action.",
    );
    expect(screen.getByText("Chain-of-thought")).toBeInTheDocument();
    expect(screen.getByText("Enabled by policy")).toBeInTheDocument();
  });
});

