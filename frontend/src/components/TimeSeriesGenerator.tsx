import { GenerationForm } from "./GenerationForm";
import type { GeneratorProps } from "../types";

export function TimeSeriesGenerator(props: GeneratorProps) {
  return <GenerationForm {...props} kind="timeseries" />;
}
