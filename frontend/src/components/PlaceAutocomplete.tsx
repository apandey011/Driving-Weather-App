import { useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";
import { useMapsLibrary } from "@vis.gl/react-google-maps";

interface RecentLocation {
  display: string;
  query: string;
}

interface Props {
  placeholder: string;
  onPlaceSelect?: (query: string) => void;
  onManualEdit?: () => void;
  onCurrentLocation?: (lat: number, lng: number) => void;
  recentLocations?: RecentLocation[];
  required?: boolean;
}

const PlaceAutocomplete = forwardRef<HTMLInputElement, Props>(
  ({ placeholder, onPlaceSelect, onManualEdit, onCurrentLocation, recentLocations = [], required }, ref) => {
    const inputRef = useRef<HTMLInputElement>(null);
    const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);
    const wrapperRef = useRef<HTMLDivElement>(null);
    const onPlaceSelectRef = useRef(onPlaceSelect);
    onPlaceSelectRef.current = onPlaceSelect;
    const onManualEditRef = useRef(onManualEdit);
    onManualEditRef.current = onManualEdit;
    const places = useMapsLibrary("places");
    const [showDropdown, setShowDropdown] = useState(false);
    const [geoLoading, setGeoLoading] = useState(false);

    const hasDropdownItems = !!onCurrentLocation || recentLocations.length > 0;

    useImperativeHandle(ref, () => inputRef.current!);

    useEffect(() => {
      if (!places || !inputRef.current) return;

      autocompleteRef.current = new places.Autocomplete(inputRef.current, {
        fields: ["formatted_address", "place_id"],
      });

      autocompleteRef.current.addListener("place_changed", () => {
        const place = autocompleteRef.current?.getPlace();
        if (place?.formatted_address && onPlaceSelectRef.current) {
          const query = place.place_id
            ? `place_id:${place.place_id}`
            : place.formatted_address;
          onPlaceSelectRef.current(query);
        }
        setShowDropdown(false);
      });
    }, [places]);

    // Close dropdown when clicking outside
    useEffect(() => {
      function handleClickOutside(e: MouseEvent) {
        if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
          setShowDropdown(false);
        }
      }
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    function handleFocus() {
      if (hasDropdownItems && !inputRef.current?.value) {
        setShowDropdown(true);
      }
    }

    function handleInput() {
      onManualEditRef.current?.();
      if (inputRef.current?.value) {
        setShowDropdown(false);
      } else if (hasDropdownItems) {
        setShowDropdown(true);
      }
    }

    function handleUseLocation() {
      if (!navigator.geolocation || !onCurrentLocation) return;
      setGeoLoading(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          onCurrentLocation(latitude, longitude);
          setShowDropdown(false);

          const geocoder = new google.maps.Geocoder();
          geocoder.geocode(
            { location: { lat: latitude, lng: longitude } },
            (results, status) => {
              if (inputRef.current) {
                inputRef.current.value =
                  status === "OK" && results?.[0]?.formatted_address
                    ? results[0].formatted_address
                    : `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
              }
              setGeoLoading(false);
            },
          );
        },
        () => {
          setGeoLoading(false);
          setShowDropdown(false);
        },
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
      );
    }

    function handleRecentSelect(loc: RecentLocation) {
      if (inputRef.current) inputRef.current.value = loc.display;
      onPlaceSelect?.(loc.query);
      setShowDropdown(false);
    }

    return (
      <div className="place-autocomplete-wrapper" ref={wrapperRef}>
        <input
          ref={inputRef}
          type="text"
          placeholder={placeholder}
          onFocus={handleFocus}
          onInput={handleInput}
          required={required}
        />
        {showDropdown && hasDropdownItems && (
          <div className="current-location-dropdown">
            {onCurrentLocation && (
              <button
                type="button"
                className="current-location-option"
                onMouseDown={(e) => e.preventDefault()}
                onClick={handleUseLocation}
                disabled={geoLoading}
              >
                <span className="current-location-icon">{geoLoading ? "..." : "\u{1F4CD}"}</span>
                <span className="current-location-text">
                  {geoLoading ? "Getting location..." : "Use current location"}
                </span>
              </button>
            )}
            {recentLocations.length > 0 && onCurrentLocation && (
              <div className="dropdown-divider" />
            )}
            {recentLocations.map((loc, idx) => (
              <button
                key={idx}
                type="button"
                className="current-location-option"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleRecentSelect(loc)}
              >
                <span className="current-location-icon">{"\u{1F552}"}</span>
                <span className="current-location-text">{loc.display}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  },
);

export default PlaceAutocomplete;
