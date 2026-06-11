import { Orb } from "orb-ui";
import type { OrbState } from "orb-ui";
import { ChatUI } from "./ChatUI";

type PreviewOrbProps = {
  state: OrbState;
  volume: number;
};

function AgentUI({ state, volume }: PreviewOrbProps): React.JSX.Element {
  return (
    <div className="flex flex-col items-center gap-6">
      <Orb
        size={350}
        state={state}
        volume={volume}
        theme={state === "listening" ? "bars" : "circle"}
      />
      <ChatUI state={state} />
    </div>
  );
}

export { AgentUI as PreviewOrb };
