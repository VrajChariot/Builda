import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

type UseMicVolumeReturnType = [
  volume: number,
  isListening: boolean,
  setisListening: Dispatch<SetStateAction<boolean>>,
];

export const useMicVolume = (): UseMicVolumeReturnType => {
  const [volume, setvolume] = useState(0);
  const [isListening, setisListening] = useState(false);

  useEffect(() => {
    if (!isListening) {
      setvolume(0);
      return;
    }

    let audioStream: MediaStream | null = null;
    let audioContext: AudioContext | null = null;
    let volumeInterval: number | null = null;
    let isCancelled = false;

    const startAnalyzing = async () => {
      try {
        audioStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
          },
        });

        if (isCancelled) {
          audioStream.getTracks().forEach((track) => track.stop());
          return;
        }

        audioContext = new AudioContext();
        const audioSource = audioContext.createMediaStreamSource(audioStream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        analyser.minDecibels = -127;
        analyser.maxDecibels = 0;
        analyser.smoothingTimeConstant = 0.3;
        audioSource.connect(analyser);

        const waveform = new Uint8Array(analyser.fftSize);

        const updateVolume = () => {
          analyser.getByteTimeDomainData(waveform);
          let sumSquares = 0;

          for (const currentVolume of waveform) {
            const normalizedSample = (currentVolume - 128) / 128;
            sumSquares += normalizedSample * normalizedSample;
          }

          const rmsVolume = Math.sqrt(sumSquares / waveform.length);
          const boostedVolume = Math.min(
            1,
            Math.pow(Math.max(rmsVolume - 0.001, 0), 0.35) * 2.1,
          );

          setvolume(
            (currentVolume) => currentVolume * 0.3 + boostedVolume * 0.7,
          );
        };

        updateVolume();
        // Updating every 16ms keeps the orb responsive and more aggressive.
        volumeInterval = window.setInterval(updateVolume, 16);
      } catch (error) {
        console.log("error while analysing volume", error);
        setisListening(false);
      }
    };

    void startAnalyzing();

    return () => {
      isCancelled = true;
      if (volumeInterval !== null) {
        window.clearInterval(volumeInterval);
      }
      audioStream?.getTracks().forEach((track) => track.stop());
      void audioContext?.close();
    };
  }, [isListening]);

  return [volume, isListening, setisListening];
};
