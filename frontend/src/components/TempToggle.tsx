interface Props {
  useFahrenheit: boolean;
  onToggle: () => void;
}

export default function TempToggle({ useFahrenheit, onToggle }: Props) {
  return (
    <button className="temp-toggle" onClick={onToggle} aria-label="Toggle temperature unit">
      {useFahrenheit ? "\u00B0F" : "\u00B0C"}
    </button>
  );
}
