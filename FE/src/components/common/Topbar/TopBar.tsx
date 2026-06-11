import { ThemeToggle } from "./ThemeToggle";
import { StatusBagde } from "./statusBagde";

function TopBar(): React.JSX.Element {
  return (
    <nav className="flex items-center justify-between px-20 py-4 border-b sticky top-0 z-10">
      <h1 className="text-2xl font-bold">Builda AI</h1>
      <div className="flex items-center gap-4">
        <StatusBagde />
        <ThemeToggle />
      </div>
    </nav>
  );
}

export { TopBar };
