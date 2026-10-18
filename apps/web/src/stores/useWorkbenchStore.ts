import { create } from "zustand";

import {
  createEpisode,
  createProject,
  createScene,
  createShot,
  executeUcodeRun,
  extractSourceText,
  fetchPlanningDrafts,
  fetchProject,
  fetchProjects,
  fetchSourceFiles,
  fetchSourceTextExtractions,
  fetchUcodeRuns,
  hardDeleteProject,
  applyPlanningDraft,
  saveIntakeSource,
  renameHierarchy,
  setHierarchyArchived,
  setProjectArchived,
  updateProjectCreativeGoal,
  updateProject,
  uploadSourceFile,
} from "../services/api";
import type { UcodeAction } from "../data/actions";
import type { SystemPromptStatus } from "../types/system";
import type {
  CommandDraft,
  IntakeDraft,
  ProjectDetail,
  ProjectSummary,
  SourceInputCategory,
  SourceFile,
  UcodeRun,
} from "../types/workbench";
import type { PlanningDraft, SourceTextExtraction } from "../types/planning";
import type { CreativeGoal } from "../utils/creativeGoal";

const GOAL_STORAGE_KEY = "ai-director-creative-goal";
const ACTIVE_PROJECT_STORAGE_KEY = "ai-director-active-project-id";

function initialCreativeGoal(): CreativeGoal {
  if (typeof window === "undefined") return "full_pipeline";
  const value = window.localStorage.getItem(GOAL_STORAGE_KEY);
  return value === "prompt_storyboard" ||
    value === "asset_only" ||
    value === "analysis_plan" ||
    value === "full_pipeline"
    ? value
    : "full_pipeline";
}

function storedActiveProjectId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
}

function rememberActiveProject(projectId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, projectId);
}

function forgetActiveProject(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
}

type Selection = {
  episodeId?: string;
  sceneId?: string;
  shotId?: string;
};

function firstAvailableSelection(project: ProjectDetail): Selection {
  const episode = project.episodes.find((item) => !item.is_archived);
  const scene = episode?.scenes.find((item) => !item.is_archived);
  const shot = scene?.shots.find((item) => !item.is_archived);
  return {
    episodeId: episode?.id,
    sceneId: scene?.id,
    shotId: shot?.id,
  };
}

function resolveScope(
  project: ProjectDetail | null,
  selection: Selection,
  action: string,
): string {
  if (!project) return "EP01";
  const episode =
    project.episodes.find((item) => item.id === selection.episodeId) ??
    project.episodes.find((item) => !item.is_archived);
  const scene =
    episode?.scenes.find((item) => item.id === selection.sceneId) ??
    episode?.scenes.find((item) => !item.is_archived);
  const shot =
    scene?.shots.find((item) => item.id === selection.shotId) ??
    scene?.shots.find((item) => !item.is_archived);
  const episodeScope = episode?.episode_code ?? "EP01";
  const sceneScope = `${episodeScope}${scene?.scene_code ?? "SC01"}`;
  const shotScope = `${sceneScope}｜${shot?.shot_code ?? "SH001"}`;

  if (action === "start" || action === "plan") return episodeScope;
  if (action === "storyboard" || action === "video_package") return shotScope;
  return sceneScope;
}

function updateProjectList(
  projects: ProjectSummary[],
  detail: ProjectDetail,
): ProjectSummary[] {
  const summary: ProjectSummary = detail;
  const existing = projects.findIndex((project) => project.id === detail.id);
  if (existing === -1)
    return [...projects, summary].sort((a, b) =>
      a.project_code.localeCompare(b.project_code),
    );
  return projects.map((project) =>
    project.id === detail.id ? summary : project,
  );
}

type WorkbenchState = {
  systemPromptStatus: SystemPromptStatus | null;
  isLoadingStatus: boolean;
  isBusy: boolean;
  error: string | null;
  selectedAction: UcodeAction | null;
  projects: ProjectSummary[];
  activeProject: ProjectDetail | null;
  selection: Selection;
  sourceFiles: SourceFile[];
  sourceTextExtractions: SourceTextExtraction[];
  planningDrafts: PlanningDraft[];
  ucodeRuns: UcodeRun[];
  latestRun: UcodeRun | null;
  commandDraft: CommandDraft;
  creativeGoal: CreativeGoal;
  setSystemPromptStatus: (status: SystemPromptStatus) => void;
  setStatusLoading: (loading: boolean) => void;
  selectAction: (action: UcodeAction) => void;
  clearError: () => void;
  loadProjects: (options?: { restoreActive?: boolean }) => Promise<void>;
  openProject: (projectId: string) => Promise<void>;
  createProject: (name: string, description: string) => Promise<void>;
  updateActiveProject: (name: string, description: string) => Promise<void>;
  setActiveProjectArchived: (archived: boolean) => Promise<void>;
  deleteProjectPermanently: (
    projectId: string,
    confirmProjectName: string,
  ) => Promise<void>;
  addEpisode: () => Promise<void>;
  addScene: (episodeId: string) => Promise<void>;
  addShot: (sceneId: string) => Promise<void>;
  renameItem: (
    kind: "episodes" | "scenes" | "shots",
    id: string,
    name: string,
  ) => Promise<void>;
  setItemArchived: (
    kind: "episodes" | "scenes" | "shots",
    id: string,
    archived: boolean,
  ) => Promise<void>;
  setSelection: (selection: Selection) => void;
  updateCommandDraft: (draft: Partial<CommandDraft>) => void;
  setCreativeGoal: (goal: CreativeGoal) => Promise<void>;
  saveManualRecord: () => Promise<void>;
  uploadFile: (category: SourceInputCategory, file: File) => Promise<void>;
  startProjectFromIntake: (
    name: string,
    description: string,
    intake: IntakeDraft,
  ) => Promise<void>;
  attachIntakeAndStart: (intake: IntakeDraft) => Promise<void>;
  loadPlanningData: () => Promise<void>;
  applyDraft: (draftId: string) => Promise<void>;
};

export const useWorkbenchStore = create<WorkbenchState>((set, get) => ({
  systemPromptStatus: null,
  isLoadingStatus: true,
  isBusy: false,
  error: null,
  selectedAction: null,
  projects: [],
  activeProject: null,
  selection: {},
  sourceFiles: [],
  sourceTextExtractions: [],
  planningDrafts: [],
  ucodeRuns: [],
  latestRun: null,
  commandDraft: {
    action: "start",
    scopeCode: "EP01",
    additionalRequest: "",
  },
  creativeGoal: initialCreativeGoal(),
  setSystemPromptStatus: (systemPromptStatus) =>
    set({ systemPromptStatus, isLoadingStatus: false }),
  setStatusLoading: (isLoadingStatus) => set({ isLoadingStatus }),
  selectAction: (selectedAction) => {
    const { activeProject, selection } = get();
    set({
      selectedAction,
      commandDraft: {
        action: selectedAction.code,
        scopeCode: resolveScope(activeProject, selection, selectedAction.code),
        additionalRequest: "",
      },
    });
  },
  clearError: () => set({ error: null }),
  loadProjects: async (options) => {
    set({ isBusy: true, error: null });
    try {
      const projects = await fetchProjects(true);
      set({ projects, isBusy: false });
      if (options?.restoreActive === false) return;
      const activeProject = get().activeProject;
      const rememberedProject = projects.find(
        (project) =>
          project.id === storedActiveProjectId() && !project.is_archived,
      );
      const latestOpenProject = [...projects]
        .filter((project) => !project.is_archived)
        .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
      if (!activeProject && (rememberedProject || latestOpenProject)) {
        await get().openProject((rememberedProject || latestOpenProject)!.id);
      }
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  openProject: async (projectId) => {
    set({ isBusy: true, error: null });
    try {
      const [
        activeProject,
        sourceFiles,
        ucodeRuns,
        sourceTextExtractions,
        planningDrafts,
      ] = await Promise.all([
        fetchProject(projectId),
        fetchSourceFiles(projectId),
        fetchUcodeRuns(projectId),
        fetchSourceTextExtractions(projectId),
        fetchPlanningDrafts(projectId),
      ]);
      const selection = firstAvailableSelection(activeProject);
      const action = get().commandDraft.action;
      rememberActiveProject(activeProject.id);
      set({
        activeProject,
        sourceFiles,
        sourceTextExtractions,
        planningDrafts,
        ucodeRuns,
        latestRun: ucodeRuns[0] ?? null,
        creativeGoal: activeProject.creative_goal,
        selection,
        commandDraft: {
          ...get().commandDraft,
          scopeCode: resolveScope(activeProject, selection, action),
        },
        isBusy: false,
      });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  createProject: async (name, description) => {
    set({ isBusy: true, error: null });
    try {
      const activeProject = await createProject(name, description);
      set({
        projects: updateProjectList(get().projects, activeProject),
        isBusy: false,
      });
      await get().openProject(activeProject.id);
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  updateActiveProject: async (name, description) => {
    const project = get().activeProject;
    if (!project) return;
    set({ isBusy: true, error: null });
    try {
      const activeProject = await updateProject(project.id, name, description);
      set({
        activeProject,
        projects: updateProjectList(get().projects, activeProject),
        isBusy: false,
      });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  setActiveProjectArchived: async (archived) => {
    const project = get().activeProject;
    if (!project) return;
    set({ isBusy: true, error: null });
    try {
      const activeProject = await setProjectArchived(project.id, archived);
      set({
        activeProject,
        projects: updateProjectList(get().projects, activeProject),
        isBusy: false,
      });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  deleteProjectPermanently: async (projectId, confirmProjectName) => {
    set({ isBusy: true, error: null });
    try {
      await hardDeleteProject(projectId, confirmProjectName);
      const isActiveDeleted = get().activeProject?.id === projectId;
      if (isActiveDeleted) forgetActiveProject();
      set({
        projects: get().projects.filter((project) => project.id !== projectId),
        activeProject: isActiveDeleted ? null : get().activeProject,
        sourceFiles: isActiveDeleted ? [] : get().sourceFiles,
        sourceTextExtractions: isActiveDeleted
          ? []
          : get().sourceTextExtractions,
        planningDrafts: isActiveDeleted ? [] : get().planningDrafts,
        ucodeRuns: isActiveDeleted ? [] : get().ucodeRuns,
        latestRun: isActiveDeleted ? null : get().latestRun,
        isBusy: false,
      });
      window.dispatchEvent(new CustomEvent("flow-nav-refresh"));
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  addEpisode: async () => {
    const project = get().activeProject;
    if (!project) return;
    set({ isBusy: true, error: null });
    try {
      const activeProject = await createEpisode(project.id);
      set({ activeProject, isBusy: false });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  addScene: async (episodeId) => {
    set({ isBusy: true, error: null });
    try {
      set({ activeProject: await createScene(episodeId), isBusy: false });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  addShot: async (sceneId) => {
    set({ isBusy: true, error: null });
    try {
      set({ activeProject: await createShot(sceneId), isBusy: false });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  renameItem: async (kind, id, name) => {
    set({ isBusy: true, error: null });
    try {
      set({
        activeProject: await renameHierarchy(kind, id, name),
        isBusy: false,
      });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  setItemArchived: async (kind, id, archived) => {
    set({ isBusy: true, error: null });
    try {
      set({
        activeProject: await setHierarchyArchived(kind, id, archived),
        isBusy: false,
      });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  setSelection: (partialSelection) => {
    const selection = { ...get().selection, ...partialSelection };
    const action = get().commandDraft.action;
    set({
      selection,
      commandDraft: {
        ...get().commandDraft,
        scopeCode: resolveScope(get().activeProject, selection, action),
      },
    });
  },
  updateCommandDraft: (partialDraft) => {
    const commandDraft = { ...get().commandDraft, ...partialDraft };
    if (partialDraft.action) {
      commandDraft.scopeCode = resolveScope(
        get().activeProject,
        get().selection,
        partialDraft.action,
      );
    }
    set({ commandDraft });
  },
  setCreativeGoal: async (creativeGoal) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(GOAL_STORAGE_KEY, creativeGoal);
    }
    const project = get().activeProject;
    set({ creativeGoal, error: null });
    try {
      if (project) {
        const activeProject = await updateProjectCreativeGoal(
          project.id,
          creativeGoal,
        );
        set({
          activeProject,
          projects: updateProjectList(get().projects, activeProject),
          creativeGoal: activeProject.creative_goal,
        });
      }
      window.dispatchEvent(new CustomEvent("flow-nav-refresh"));
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },
  saveManualRecord: async () => {
    const project = get().activeProject;
    const draft = get().commandDraft;
    if (!project) return;
    set({ isBusy: true, error: null });
    try {
      const latestRun = await executeUcodeRun(
        project.id,
        draft.action,
        draft.scopeCode,
        draft.additionalRequest,
      );
      set({
        latestRun,
        ucodeRuns: [latestRun, ...get().ucodeRuns],
        isBusy: false,
      });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  startProjectFromIntake: async (name, description, intake) => {
    set({ isBusy: true, error: null });
    try {
      const project = await createProject(name, description);
      rememberActiveProject(project.id);
      const sourceFile = await saveIntakeSource(project.id, intake);
      await extractSourceText(sourceFile.id);
      const [
        activeProject,
        sourceFiles,
        ucodeRuns,
        sourceTextExtractions,
        planningDrafts,
      ] = await Promise.all([
        fetchProject(project.id),
        fetchSourceFiles(project.id),
        fetchUcodeRuns(project.id),
        fetchSourceTextExtractions(project.id),
        fetchPlanningDrafts(project.id),
      ]);
      const selection = firstAvailableSelection(activeProject);
      set({
        projects: updateProjectList(get().projects, activeProject),
        activeProject,
        sourceFiles,
        sourceTextExtractions,
        planningDrafts,
        ucodeRuns,
        latestRun: ucodeRuns[0] ?? null,
        creativeGoal: activeProject.creative_goal,
        selection,
        selectedAction: null,
        commandDraft: {
          action: "start",
          scopeCode: resolveScope(activeProject, selection, "start"),
          additionalRequest: "",
        },
        isBusy: false,
      });
      window.dispatchEvent(new CustomEvent("flow-nav-refresh"));
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  attachIntakeAndStart: async (intake) => {
    const project = get().activeProject;
    if (!project) return;
    set({ isBusy: true, error: null });
    try {
      const sourceFile = await saveIntakeSource(project.id, intake);
      await extractSourceText(sourceFile.id);
      const [sourceFiles, ucodeRuns, sourceTextExtractions, planningDrafts] =
        await Promise.all([
          fetchSourceFiles(project.id),
          fetchUcodeRuns(project.id),
          fetchSourceTextExtractions(project.id),
          fetchPlanningDrafts(project.id),
        ]);
      set({
        sourceFiles,
        sourceTextExtractions,
        planningDrafts,
        ucodeRuns,
        latestRun: ucodeRuns[0] ?? null,
        isBusy: false,
      });
      window.dispatchEvent(new CustomEvent("flow-nav-refresh"));
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  uploadFile: async (category, file) => {
    const project = get().activeProject;
    if (!project) return;
    set({ isBusy: true, error: null });
    try {
      const sourceFile = await uploadSourceFile(project.id, category, file);
      const extraction = await extractSourceText(sourceFile.id);
      set({
        sourceFiles: [sourceFile, ...get().sourceFiles],
        sourceTextExtractions: [extraction, ...get().sourceTextExtractions],
        isBusy: false,
      });
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
  loadPlanningData: async () => {
    const project = get().activeProject;
    if (!project) return;
    try {
      const [sourceTextExtractions, planningDrafts] = await Promise.all([
        fetchSourceTextExtractions(project.id),
        fetchPlanningDrafts(project.id),
      ]);
      set({ sourceTextExtractions, planningDrafts });
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },
  applyDraft: async (draftId) => {
    const project = get().activeProject;
    if (!project) return;
    set({ isBusy: true, error: null });
    try {
      await applyPlanningDraft(draftId);
      const [activeProject, planningDrafts] = await Promise.all([
        fetchProject(project.id),
        fetchPlanningDrafts(project.id),
      ]);
      set({
        activeProject,
        planningDrafts,
        isBusy: false,
      });
      window.dispatchEvent(new CustomEvent("flow-nav-refresh"));
    } catch (error) {
      set({ error: (error as Error).message, isBusy: false });
    }
  },
}));
