import { ArrowRight, Database, FolderPlus, Layers3, Plus, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useCreateProject, useProjects } from "../api/queries";
import { PageHeader } from "../components/PageHeader";
import { ProgressBar } from "../components/ProgressBar";
import { StatePanel } from "../components/StatePanel";
import { formatCount, formatDate, formatPercent } from "../components/format";

interface ProjectsViewProps {
  onGenerate: (projectId: string) => void;
}

export function ProjectsView({ onGenerate }: ProjectsViewProps) {
  const projects = useProjects();
  const createProject = useCreateProject();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanName = name.trim();
    if (!cleanName) return;
    createProject.mutate(
      { name: cleanName, description: description.trim() },
      {
        onSuccess: () => {
          setName("");
          setDescription("");
          setShowForm(false);
        },
      },
    );
  };

  return (
    <div className="view-stack">
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Keep seed data, generation recipes, review decisions, and exports organized by product use case."
        actions={
          <button className="button button--primary" type="button" onClick={() => setShowForm(true)}>
            <Plus size={17} aria-hidden="true" /> New project
          </button>
        }
      />

      {showForm ? (
        <section className="panel form-panel" aria-labelledby="new-project-title">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Create workspace</p>
              <h2 id="new-project-title">New project</h2>
            </div>
          </div>
          <form className="inline-form" onSubmit={submit}>
            <label className="field">
              <span>Project name</span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="For example: Billing support assistant"
                maxLength={80}
                required
                autoFocus
              />
            </label>
            <label className="field field--wide">
              <span>Description</span>
              <input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What this training dataset should help the model do"
                maxLength={240}
              />
            </label>
            <div className="form-actions">
              <button className="button button--secondary" type="button" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button
                className="button button--primary"
                type="submit"
                disabled={!name.trim() || createProject.isPending}
              >
                <FolderPlus size={16} aria-hidden="true" />
                {createProject.isPending ? "Creating…" : "Create project"}
              </button>
            </div>
          </form>
          {createProject.isError ? (
            <p className="form-error" role="alert">
              {createProject.error.message}
            </p>
          ) : null}
        </section>
      ) : null}

      {projects.isPending ? <StatePanel kind="loading" /> : null}
      {projects.isError ? (
        <StatePanel kind="error" message={projects.error.message} onRetry={() => void projects.refetch()} />
      ) : null}
      {projects.data && projects.data.length === 0 ? (
        <StatePanel
          kind="empty"
          title="Create your first project"
          message="A project groups the seeds, recipes, runs, review decisions, and exports for one use case."
        />
      ) : null}

      {projects.data?.length ? (
        <section className="project-grid" aria-label="Dataset projects">
          {projects.data.map((project) => {
            const acceptance = project.generatedCount
              ? project.acceptedCount / project.generatedCount
              : 0;
            return (
              <article className="project-card" key={project.id}>
                <div className="project-card__topline">
                  <span className="project-card__icon" aria-hidden="true">
                    <Layers3 size={19} />
                  </span>
                  {project.activeRunId ? <span className="live-label"><i /> Active run</span> : null}
                </div>
                <div>
                  <h2>{project.name}</h2>
                  <p>{project.description || "No project description yet."}</p>
                </div>
                <div className="project-card__stats">
                  <div>
                    <Database size={15} aria-hidden="true" />
                    <strong>{formatCount(project.seedCount)}</strong>
                    <span>seeds</span>
                  </div>
                  <div>
                    <Sparkles size={15} aria-hidden="true" />
                    <strong>{formatCount(project.generatedCount)}</strong>
                    <span>generated</span>
                  </div>
                </div>
                <ProgressBar
                  value={project.acceptedCount}
                  max={project.generatedCount || 1}
                  label={`Accepted ${formatPercent(acceptance)}`}
                  showValue={false}
                  tone="success"
                />
                <div className="project-card__footer">
                  <span>Updated {formatDate(project.lastActivity)}</span>
                  <button className="text-action" type="button" onClick={() => onGenerate(project.id)}>
                    Generate data <ArrowRight size={15} />
                  </button>
                </div>
              </article>
            );
          })}
        </section>
      ) : null}
    </div>
  );
}
