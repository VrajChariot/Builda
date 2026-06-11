import type { OrbState } from "orb-ui";
import { useTranscript } from "../context/TranscriptContext";

type ChatUIProps = {
  state: OrbState;
};

const ChatUI = ({ state }: ChatUIProps) => {
  const isAgent = state === "speaking";
  const { transcript } = useTranscript();

  return (
    <div className="flex flex-col items-center gap-4">
      <span
        className={
          isAgent
            ? "text-cyan-300 font-semibold uppercase tracking-widest text-sm"
            : "text-amber-400 font-semibold uppercase tracking-widest text-sm"
        }
      >
        {isAgent ? "Builda" : "YOU"}
      </span>
      <div className="flex items-center gap-4">
        <span
          className={
            isAgent
              ? "font-semibold text-3xl text-cyan-100 drop-shadow-[0_6px_18px_rgba(99,211,255,0.06)] text-center"
              : "font-semibold text-3xl text-white/90 text-center"
          }
        >
          {isAgent ? "Builda is building waitttt" : transcript}
        </span>
        <span className="flex items-center gap-2">
          {isAgent ? (
            <>
              <span className="dot-agent dot-agent-1 w-2 h-2 rounded-full bg-cyan-500" />
              <span className="dot-agent dot-agent-2 w-2 h-2 rounded-full bg-cyan-400" />
              <span className="dot-agent dot-agent-3 w-2 h-2 rounded-full bg-cyan-300" />
            </>
          ) : (
            <>
              <span className="dot dot-1 w-2 h-2 rounded-full bg-amber-500" />
              <span className="dot dot-2 w-2 h-2 rounded-full bg-amber-400" />
              <span className="dot dot-3 w-2 h-2 rounded-full bg-amber-300" />
            </>
          )}
        </span>
      </div>
    </div>
  );
};

export { ChatUI };
