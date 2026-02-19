import { WeatherAdvisory } from "../types";

interface Props {
  advisories: WeatherAdvisory[];
}

export default function WeatherAdvisories({ advisories }: Props) {
  if (advisories.length === 0) return null;

  return (
    <div className="advisories">
      {advisories.map((adv) => (
        <div key={`${adv.type}-${adv.severity}`} className={`advisory advisory-${adv.severity}`}>
          <span className="advisory-icon">
            {adv.severity === "danger" ? "\u26A0\uFE0F" : "\u26A0"}
          </span>
          <span className="advisory-message">{adv.message}</span>
        </div>
      ))}
    </div>
  );
}
