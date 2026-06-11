import { useDarkMode } from "@rbnd/react-dark-mode";
import sunImg from "../../../assets/sunny.png";
import moonImg from "../../../assets/moon.png";

const Theme = {
  LIGHT: "light",
  DARK: "dark",
} as const;

function ThemeToggle(): React.JSX.Element {
  const { mode, setMode } = useDarkMode();

  const isDarkMode = mode === Theme.DARK;

  const switchTheme = () => {
    setMode(isDarkMode ? Theme.LIGHT : Theme.DARK);
  };

  return (
    <button
      type="button"
      onClick={switchTheme}
      aria-label="Toggle color theme"
      className="inline-flex items-center justify-center w-10 h-8 rounded-full focus:outline-none"
    >
      {isDarkMode ? (
        <img src={sunImg} alt="Sun" className="h-5 w-5 object-contain" />
      ) : (
        <img src={moonImg} alt="Moon" className="h-5 w-5 object-contain" />
      )}
    </button>
  );
}

export { ThemeToggle };
