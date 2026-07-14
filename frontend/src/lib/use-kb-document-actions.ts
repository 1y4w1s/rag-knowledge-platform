import { useCallback, useState, type Dispatch, type SetStateAction } from "react";

import {
  deleteDocument,
  retryDocument,
  uploadDocuments,
  type Document,
} from "@/lib/document-api";
import { validateUploadFiles } from "@/lib/document-upload-validation";
import {
  PERMISSION_DENIED_MESSAGE,
  showMemberWriteBlockedToast,
} from "@/lib/member-write-message";

type ShowToast = (message: string) => void;

export function useKbDocumentActions(
  kbId: string | undefined,
  documents: Document[],
  setDocuments: Dispatch<SetStateAction<Document[]>>,
  loadDocuments: (id: string) => Promise<Document[]>,
  showToast: ShowToast,
) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);

  const clearInlineErrors = useCallback(() => {
    setUploadError(null);
    setActionError(null);
  }, []);

  const notifyPermissionDenied = useCallback(
    (message: string) => {
      if (message === "没有权限执行此操作") {
        showToast(PERMISSION_DENIED_MESSAGE);
        return true;
      }
      return false;
    },
    [showToast],
  );

  const notifyMemberWriteBlocked = useCallback(() => {
    showMemberWriteBlockedToast(showToast);
  }, [showToast]);

  const handleDeleteDocument = useCallback(
    async (docId: string): Promise<boolean> => {
      if (!kbId) return false;
      clearInlineErrors();
      try {
        await deleteDocument(kbId, docId);
        setDocuments((prev) => prev.filter((doc) => doc.id !== docId));
        return true;
      } catch (err) {
        const message = err instanceof Error ? err.message : "删除失败";
        if (notifyPermissionDenied(message)) return false;
        if (message.includes("接口不存在")) {
          setActionError(message);
          return false;
        }
        const isNotFound =
          message === "文档不存在" || message === "未找到资源";

        if (isNotFound) {
          try {
            let fresh = await loadDocuments(kbId);
            if (fresh.some((doc) => doc.id === docId)) {
              await deleteDocument(kbId, docId);
              fresh = await loadDocuments(kbId);
            }
            if (!fresh.some((doc) => doc.id === docId)) {
              return true;
            }
            setActionError(
              "删除失败且列表仍显示该文档。请点击「刷新列表」或 F5 后再试。",
            );
            return false;
          } catch (retryErr) {
            const retryMsg =
              retryErr instanceof Error ? retryErr.message : "删除失败";
            setActionError(retryMsg);
            return false;
          }
        }
        setActionError(message);
        return false;
      }
    },
    [
      kbId,
      clearInlineErrors,
      notifyPermissionDenied,
      loadDocuments,
      setDocuments,
    ],
  );

  const handleRetryDocument = useCallback(
    async (docId: string) => {
      if (!kbId) return;
      clearInlineErrors();
      try {
        const updated = await retryDocument(kbId, docId);
        setDocuments((prev) =>
          prev.map((doc) => (doc.id === docId ? updated : doc)),
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : "重试失败";
        if (notifyPermissionDenied(message)) return;
        if (message.includes("接口不存在")) {
          setActionError(message);
          return;
        }
        const isNotFound =
          message === "文档不存在" || message === "未找到资源";

        if (isNotFound) {
          try {
            const fresh = await loadDocuments(kbId);
            if (!fresh.some((doc) => doc.id === docId)) {
              return;
            }
            const updated = await retryDocument(kbId, docId);
            setDocuments((prev) =>
              prev.map((doc) => (doc.id === docId ? updated : doc)),
            );
          } catch (retryErr) {
            const retryMsg =
              retryErr instanceof Error ? retryErr.message : "重试失败";
            setActionError(retryMsg);
          }
          return;
        }
        setActionError(message);
      }
    },
    [
      kbId,
      clearInlineErrors,
      notifyPermissionDenied,
      loadDocuments,
      setDocuments,
    ],
  );

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;

    const docId = deleteTarget.id;
    setDeletingDocId(docId);
    try {
      const ok = await handleDeleteDocument(docId);
      if (ok) setDeleteTarget(null);
    } finally {
      setDeletingDocId(null);
    }
  }, [deleteTarget, handleDeleteDocument]);

  const handleUpload = useCallback(
    async (files: File[]) => {
      if (!kbId) return;

      const validation = validateUploadFiles(
        files,
        documents.map((doc) => doc.filename),
      );
      if (!validation.ok) {
        setUploadError(validation.message);
        return;
      }

      setUploading(true);
      clearInlineErrors();
      try {
        await uploadDocuments(kbId, validation.files);
        await loadDocuments(kbId);
      } catch (err) {
        const message = err instanceof Error ? err.message : "上传失败";
        if (notifyPermissionDenied(message)) return;
        setUploadError(message);
      } finally {
        setUploading(false);
      }
    },
    [
      kbId,
      documents,
      clearInlineErrors,
      loadDocuments,
      notifyPermissionDenied,
    ],
  );

  return {
    uploading,
    uploadError,
    actionError,
    deleteTarget,
    deletingDocId,
    clearInlineErrors,
    notifyMemberWriteBlocked,
    setDeleteTarget,
    handleDeleteConfirm,
    handleRetryDocument,
    handleUpload,
  };
}
