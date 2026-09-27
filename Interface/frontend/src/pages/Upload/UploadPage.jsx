import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trash2, Eye } from "lucide-react";
import AppShell from "../../components/layout/AppShell";
import Card, { CardHeader } from "../../components/common/Card";
import DropzoneUploader from "../../components/upload/DropzoneUploader";
import Button from "../../components/common/Button";
import { recentUploads } from "../../mock/mockData";
import { ROUTES } from "../../constants/routes";

export default function UploadPage() {
  const navigate = useNavigate();
  const [uploads] = useState(recentUploads);

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-[26px] font-semibold text-ink tracking-tight">
          Upload Dataset
        </h1>
        <p className="text-sm text-ink-secondary mt-1">
          Upload a CSV file to get started with your AutoML pipeline.
        </p>
      </div>

      <DropzoneUploader onFileSelected={() => {}} />

      <Card className="mt-6" padding="p-0">
        <div className="px-5 pt-5">
          <CardHeader
            title="Recent Uploads"
            subtitle="Datasets already in your workspace"
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-surface-border text-left text-[11px] uppercase tracking-wide text-ink-muted">
                <th className="font-medium px-5 py-2.5">Name</th>
                <th className="font-medium px-5 py-2.5">Rows</th>
                <th className="font-medium px-5 py-2.5">Columns</th>
                <th className="font-medium px-5 py-2.5">Uploaded At</th>
                <th className="font-medium px-5 py-2.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((ds) => (
                <tr
                  key={ds.id}
                  className="border-t border-surface-border hover:bg-surface-page/60 transition-default"
                >
                  <td className="px-5 py-3 font-medium text-ink whitespace-nowrap">
                    {ds.name}
                  </td>
                  <td className="px-5 py-3 text-ink-secondary">
                    {ds.rows.toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-ink-secondary">
                    {ds.columns}
                  </td>
                  <td className="px-5 py-3 text-ink-muted whitespace-nowrap">
                    {ds.uploadedAt}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => navigate(ROUTES.TRAINING)}
                        className="p-1.5 rounded-md text-ink-secondary hover:text-orange hover:bg-orange-50 transition-default"
                        aria-label="View dataset"
                      >
                        <Eye size={15} />
                      </button>
                      <button
                        className="p-1.5 rounded-md text-ink-secondary hover:text-state-error hover:bg-[#FCEAEA] transition-default"
                        aria-label="Delete dataset"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex justify-end mt-6">
        <Button onClick={() => navigate(ROUTES.TRAINING)}>
          Continue to Preprocessing
        </Button>
      </div>
    </AppShell>
  );
}
