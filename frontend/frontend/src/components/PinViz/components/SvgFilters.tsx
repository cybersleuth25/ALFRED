export function SvgFilters() {
  return (
    <svg
      aria-hidden="true"
      style={{ position: 'absolute', width: 0, height: 0 }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <filter id="tt-tooltip-outline">
          <feDropShadow
            dx="0"
            dy="0"
            stdDeviation="8"
            floodColor="#ECFF0F"
            floodOpacity="1"
            result="blur"
          />
          <feColorMatrix
            in="blur"
            mode="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 32 -1"
            result="outline"
          />
          <feFlood floodColor="#ECFF0F" floodOpacity="1" result="offsetColor" />
          <feComposite in="offsetColor" in2="outline" operator="in" result="offsetBlur" />
          <feBlend in="SourceGraphic" in2="offsetBlur" />
        </filter>
      </defs>
    </svg>
  );
}
