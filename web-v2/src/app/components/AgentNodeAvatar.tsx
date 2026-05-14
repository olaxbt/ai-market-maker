import { useState } from "react";
import { cn } from "./ui/utils";
import { agentAvatarPublicPath } from "../../lib/agentAvatars";

export function AgentNodeAvatar({
  nodeId,
  className,
  sizeClassName = "h-10 w-10",
}: {
  nodeId: string;
  className?: string;
  sizeClassName?: string;
}) {
  const id = (nodeId ?? "").trim() || "—";
  const src = agentAvatarPublicPath(id);
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className={cn(
          "flex shrink-0 items-center justify-center rounded-full border border-border bg-muted font-mono text-[10px] font-semibold text-muted-foreground",
          sizeClassName,
          className,
        )}
        aria-hidden
      >
        {id.slice(0, 3)}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt=""
      className={cn("shrink-0 rounded-full border border-border object-cover", sizeClassName, className)}
      onError={() => setFailed(true)}
    />
  );
}
