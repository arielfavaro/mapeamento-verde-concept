import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { JobRequest, JobSummary } from "./types";

export const isActive = (job: Pick<JobSummary, "state">) => job.state === "queued" || job.state === "running";

export const useConfig = () => useQuery({ queryKey: ["config"], queryFn: api.config, staleTime: Infinity });
export const useSensors = () => useQuery({ queryKey: ["sensors"], queryFn: api.sensors, staleTime: Infinity });
export const useIndices = () => useQuery({ queryKey: ["indices"], queryFn: api.indices, staleTime: Infinity });
export const usePresets = () => useQuery({ queryKey: ["presets"], queryFn: api.presets, staleTime: Infinity });

export const useColormap = (name: string | null) =>
  useQuery({ queryKey: ["colormap", name], queryFn: () => api.colormap(name as string), enabled: name !== null, staleTime: Infinity });

export const useSceneSearch = () => useMutation({ mutationFn: api.searchScenes });

export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: (q) => (q.state.data?.some(isActive) ? 2000 : false),
  });
}

export function useJob(id: string | null) {
  return useQuery({
    queryKey: ["jobs", id],
    queryFn: () => api.job(id as string),
    enabled: id !== null,
    refetchInterval: (q) => (q.state.data && isActive(q.state.data) ? 1500 : false),
  });
}

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: JobRequest) => api.createJob(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}
