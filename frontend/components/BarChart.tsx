export function BarChart({
  data,
  color = "#1f4e79",
  height = 140,
  label,
}: {
  data: { label: string; value: number }[];
  color?: string;
  height?: number;
  label: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const barWidth = 100 / Math.max(1, data.length);
  const showEvery = data.length > 16 ? Math.ceil(data.length / 8) : 1;
  return (
    <figure className="w-full">
      <svg viewBox={`0 0 100 ${height / 3}`} preserveAspectRatio="none" className="h-[140px] w-full" role="img" aria-label={label}>
        {data.map((d, i) => {
          const h = (d.value / max) * (height / 3 - 2);
          return (
            <rect key={d.label} x={i * barWidth + barWidth * 0.12} y={height / 3 - h} width={barWidth * 0.76} height={h} fill={color} rx={0.4}>
              <title>{`${d.label}: ${d.value}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="mt-1 flex text-[10px] text-muted">
        {data.map((d, i) => (
          <span key={d.label} className="text-center" style={{ width: `${barWidth}%` }}>
            {i % showEvery === 0 ? d.label : ""}
          </span>
        ))}
      </div>
      <figcaption className="sr-only">{label}</figcaption>
      <table className="sr-only">
        <tbody>
          {data.map((d) => (
            <tr key={d.label}>
              <td>{d.label}</td>
              <td>{d.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
