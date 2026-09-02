export type ProjectTitleInput = {
  project_name?: string | null;
  project_id: string;
};

export function projectTitle(project: ProjectTitleInput) {
  return project.project_name?.trim() || 'ไม่พบชื่อโครงการในชุดข้อมูล';
}
