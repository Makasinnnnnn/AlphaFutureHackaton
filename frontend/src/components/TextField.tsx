import { type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string; suffix?: string };

export function TextField({ id, label, suffix, className = "", ...input }: Props) {
  return <div className={`text-field${suffix ? " with-suffix" : ""}`}>
    <label htmlFor={id}>{label}</label>
    <input {...input} id={id} className={`input ${className}`} />
    {suffix && <span className="text-field-suffix" aria-hidden="true">{suffix}</span>}
  </div>;
}
