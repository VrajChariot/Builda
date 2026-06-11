function StatusBagde(): React.JSX.Element {
  return (
    <div className="flex items-center gap-3 px-4 py-1 rounded-full border border-gray-700 shadow-sm">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75 animate-ping"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
      </span>
      <span className="text-sm font-medium">Online</span>
    </div>
  );
}

export { StatusBagde };
