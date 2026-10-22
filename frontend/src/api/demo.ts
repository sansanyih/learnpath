import { api } from "./request";
import type { DemoPlan } from "./demoTypes";

export const demoApi = {
  plan: () => api.get<DemoPlan>("/api/demo/plan"),
};
