import { cn } from "./cn";
import { controlClass } from "./Field";

export function TextInput({
  invalid,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return <input type="text" className={cn(controlClass(invalid), className)} {...props} />;
}
