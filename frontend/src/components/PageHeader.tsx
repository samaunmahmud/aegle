import type { ReactNode } from "react";

export function PageHeader({
  icon,
  title,
  subtitle,
  actions,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div className="page-title">
        {icon && <div className="page-title-icon">{icon}</div>}
        <div>
          <h1>{title}</h1>
          {subtitle && <div className="page-subtitle">{subtitle}</div>}
        </div>
      </div>
      {actions && <div className="toolbar">{actions}</div>}
    </div>
  );
}
