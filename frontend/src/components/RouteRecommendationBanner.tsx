import { RouteRecommendation, RouteWithWeather } from "../types";
import { formatDuration } from "../utils";

interface Props {
  recommendation: RouteRecommendation;
  routes: RouteWithWeather[];
  selectedRouteIndex: number | null;
  onRouteSelect: (index: number) => void;
}

export default function RouteRecommendationBanner({
  recommendation,
  routes,
  selectedRouteIndex,
  onRouteSelect,
}: Props) {
  const recIdx = recommendation.recommended_route_index;
  const recScore = recommendation.scores[recIdx];

  return (
    <div className="recommendation-banner">
      <div className="recommendation-header">
        <span className="recommendation-badge">Recommended</span>
        <span className="recommendation-reason">
          {recScore.recommendation_reason}
        </span>
      
      <span className="route-scores">
        {routes.map((route, idx) => {
          const score = recommendation.scores[idx];
          const isRecommended = idx === recIdx;
          const isSelected = idx === selectedRouteIndex;
          return (
            <button
              key={idx}
              className={`route-score-chip${isRecommended ? " recommended" : ""}${isSelected ? " selected" : ""}`}
              onClick={() => onRouteSelect(route.route_index)}
              aria-label={`${route.summary || `Route ${idx + 1}`}, score ${Math.round(score.overall_score)}${isRecommended ? ", recommended" : ""}`}
              aria-pressed={isSelected}
            >
              <span className="score-value">
                {Math.round(score.overall_score)}
              </span>
              <span className="score-label">
                {route.summary || `Route ${idx + 1}`}
              </span>
              <span className="score-detail">
                {formatDuration(route.total_duration_minutes)}
              </span>
            </button>
          );
        })}
      </span>
    </div>
  </div>
  );
}
