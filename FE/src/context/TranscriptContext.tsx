import {
  createContext,
  useContext,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";

type TranscriptContextValue = {
  transcript: string;
  setTranscript: Dispatch<SetStateAction<string>>;
};

const TranscriptContext = createContext<TranscriptContextValue | null>(null);

function TranscriptProvider({
  children,
}: {
  children: ReactNode;
}): React.JSX.Element {
  const [transcript, setTranscript] = useState("");

  return (
    <TranscriptContext.Provider value={{ transcript, setTranscript }}>
      {children}
    </TranscriptContext.Provider>
  );
}

function useTranscript(): TranscriptContextValue {
  const context = useContext(TranscriptContext);

  if (context === null) {
    throw new Error("useTranscript must be used within a TranscriptProvider");
  }

  return context;
}

export { TranscriptProvider, useTranscript };
