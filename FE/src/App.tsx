import { useEffect, useState } from "react";
import type { OrbState } from "orb-ui";
import { useMicVolume } from "./hooks/useMicVolume";
import { PreviewOrb } from "./components/AgentUI";
import { TopBar } from "./components/common/Topbar/TopBar";
import { ChatControls } from "./components/common/ChatControls";
import { TranscriptProvider } from "./context/TranscriptContext";

function App() {
  const [volume, , setisListening] = useMicVolume();
  const [isChatActive, setIsChatActive] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  const state: OrbState = isChatActive ? "listening" : "speaking";
  const displayedVolume = isMuted ? 0 : volume;

  useEffect(() => {
    setisListening(isChatActive && !isMuted);
  }, [isChatActive, isMuted, setisListening]);

  return (
    <TranscriptProvider>
      <div className="flex flex-col h-dvh overflow-hidden">
        <TopBar />
        <div className="flex items-center justify-center h-full">
          <PreviewOrb state={state} volume={displayedVolume} />
        </div>
        <div className="flex justify-center mb-6">
          <ChatControls
            isListening={isChatActive}
            isMuted={isMuted}
            onStartChat={() => {
              setIsChatActive(true);
              setIsMuted(false);
            }}
            onToggleMute={() => setIsMuted((currentMuted) => !currentMuted)}
            onStopChat={() => {
              setIsChatActive(false);
              setisListening(false);
              setIsMuted(false);
            }}
          />
        </div>
      </div>
    </TranscriptProvider>
  );
}

export default App;
