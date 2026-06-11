import { Mic, MicOff, Play, Square } from "lucide-react";
import SpeechRecognition, {
  useSpeechRecognition,
} from "react-speech-recognition";
import { useEffect } from "react";
import { useTranscript } from "../../context/TranscriptContext";
type ChatControlsProps = {
  isListening: boolean;
  isMuted: boolean;
  onStartChat: () => void | Promise<void>;
  onToggleMute: () => void;
  onStopChat: () => void;
};

const ChatControls = ({
  isListening,
  isMuted,
  onStartChat,
  onToggleMute,
  onStopChat,
}: ChatControlsProps) => {
  const { transcript, resetTranscript, browserSupportsSpeechRecognition } =
    useSpeechRecognition();
  const { setTranscript } = useTranscript();

  useEffect(() => {
    setTranscript(transcript);
  }, [setTranscript, transcript]);

  if (!browserSupportsSpeechRecognition) {
    return <span>Browser doesn't support speech recognition.</span>;
  }

  const handleStartChat = () => {
    resetTranscript();
    onStartChat();
    SpeechRecognition.startListening({ continuous: true });
  };

  const handleStopeChat = () => {
    onStopChat();
    SpeechRecognition.stopListening();
    resetTranscript();
    setTranscript("");
  };

  const handleToggleMute = () => {
    onToggleMute();
    if (isMuted) {
      SpeechRecognition.startListening({ continuous: true });
    } else {
      SpeechRecognition.stopListening();
    }
  };

  return (
    <div className="flex items-center gap-3 px-3.5 py-3 border rounded-full left-1/2 shadow-[0_8px_24px_-10px_rgba(255,255,255,0.55),0_2px_8px_rgba(255,255,255,0.4),inset_0_1px_0_rgba(255,255,255,0.25)]">
      <button
        onClick={handleStartChat}
        className="flex items-center gap-2.25 px-5.5 py-3.25 text-[15px] border rounded-full shadow-[0_6px_16px_-4px_rgba(255,255,255,0.6),inset_0_1px_0_rgba(255,255,255,0.25)]"
      >
        <Play /> {isListening ? "Listening" : "Start Chat"}
      </button>
      <button
        onClick={handleToggleMute}
        disabled={!isListening}
        aria-pressed={isListening && isMuted}
        className="flex items-center justify-center gap-2 w-13 h-13 rounded-full border shadow-[0_1px_2px_rgba(255,255,255,0.6),0_2px_8px_rgba(255,255,255,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isListening && isMuted ? <MicOff /> : <Mic />}
      </button>
      <button
        onClick={handleStopeChat}
        className="flex items-center justify-center gap-2 w-13 h-13 rounded-full border shadow-[0_1px_2px_rgba(255,255,255,0.6),0_2px_8px_rgba(255,255,255,0.5)]"
      >
        <Square />
      </button>
    </div>
  );
};

export { ChatControls };
