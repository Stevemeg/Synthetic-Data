import { GenerationForm } from "./GenerationForm";
import type { GeneratorProps } from "../types";

export function ImageGenerator(props: GeneratorProps) {
  return <GenerationForm {...props} kind="imaging" />;
}
