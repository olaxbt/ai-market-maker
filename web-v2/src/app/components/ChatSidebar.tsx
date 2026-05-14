import { NavLink } from "react-router";
import { MessageSquare, Plus, Settings, BarChart3, LineChart, Activity } from "lucide-react";
import React, { useState } from "react";

interface ChatSession {
  id: string;
  title: string;
  timestamp: string;
}

interface ChatSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  sessions: ChatSession[];
  activeSessionId: string;
  onSessionSelect: (id: string) => void;
  onNewChat: () => void;
}

export default function ChatSidebar({
  isOpen,
  onToggle,
  sessions,
  activeSessionId,
  onSessionSelect,
  onNewChat
}: ChatSidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          w-64 bg-sidebar border-r border-sidebar-border
          transform transition-transform duration-200 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          flex flex-col
        `}
      >
        {/* Header */}
        <div className="p-4 border-b border-sidebar-border">
          <button
            onClick={onNewChat}
            className="w-full flex items-center gap-2 px-4 py-2.5 rounded-lg bg-sidebar-primary text-sidebar-primary-foreground hover:opacity-90 transition-opacity"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>

          <div className="mt-4 space-y-1">
            <div className="px-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              App
            </div>
            <NavLink
              to="/leaderboard"
              className={({ isActive }) =>
                [
                  "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors",
                  isActive ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent/50",
                ].join(" ")
              }
            >
              <BarChart3 className="w-4 h-4" />
              Leaderboard
            </NavLink>
            <NavLink
              to="/backtests"
              className={({ isActive }) =>
                [
                  "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors",
                  isActive ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent/50",
                ].join(" ")
              }
            >
              <LineChart className="w-4 h-4" />
              Backtests
            </NavLink>
            <NavLink
              to="/console"
              className={({ isActive }) =>
                [
                  "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors",
                  isActive ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent/50",
                ].join(" ")
              }
            >
              <Activity className="w-4 h-4" />
              Console
            </NavLink>
          </div>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-2">
          <div className="space-y-1">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSessionSelect(session.id)}
                className={`
                  w-full text-left px-3 py-2.5 rounded-lg
                  flex items-start gap-2
                  transition-colors
                  ${activeSessionId === session.id
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                  }
                `}
              >
                <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="truncate">{session.title}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {session.timestamp}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-sidebar-border">
          <button className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition-colors">
            <Settings className="w-4 h-4" />
            Settings
          </button>
        </div>
      </aside>
    </>
  );
}
