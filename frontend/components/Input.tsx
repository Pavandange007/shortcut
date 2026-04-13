"use client";

type InputProps = {
  value: string;
  onChange: (next: string) => void;
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  type?: "text" | "password" | "email";
};

export default function Input({
  value,
  onChange,
  label,
  placeholder,
  disabled,
  type = "text",
}: InputProps) {
  const hasValue = value.trim().length > 0;

  return (
    <label className="relative block">
      <input
        className="peer h-12 w-full rounded-2xl border border-white/10 bg-surface-1/70 px-4 pt-5 text-sm text-foreground placeholder-transparent transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-accent/60 disabled:cursor-not-allowed disabled:opacity-60"
        value={value}
        type={type}
        placeholder={placeholder || label || " "}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
      <span
        className={[
          "pointer-events-none absolute left-4 top-3 text-xs text-muted-foreground transition-all duration-200",
          hasValue ? "top-1.5 text-[10px] text-accent-2" : "",
          "peer-focus:top-1.5 peer-focus:text-[10px] peer-focus:text-accent-2",
        ].join(" ")}
      >
        {label || placeholder || "Input"}
      </span>
    </label>
  );
}

