import { useEffect, useState, useRef } from 'react'
import api from '../services/api'
import type { Document } from '../types'
import { Upload, Trash2, FileText, Link as LinkIcon, X, MoreVertical, Loader2 } from 'lucide-react'

interface DuplicateInfo {
  source_id: string
  existing_doc_id: string
  existing_title: string
  message: string
  source: { type: string; value: string }
}

export default function Documents() {
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [url, setUrl] = useState('')
  const [tags, setTags] = useState('')
  const [importing, setImporting] = useState(false)
  const [uploadingFile, setUploadingFile] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const [duplicates, setDuplicates] = useState<DuplicateInfo[]>([])
  const [pendingSources, setPendingSources] = useState<{ type: string; value: string }[]>([])
  const [pendingTags, setPendingTags] = useState<string[]>([])
  const [retryingId, setRetryingId] = useState<string | null>(null)

  const loadDocs = () => {
    api.get('/documents').then((res) => setDocs(res.data)).finally(() => setLoading(false))
  }

  useEffect(() => { loadDocs() }, [])

  const parseTags = (raw: string): string[] =>
    raw.split(',').map((t) => t.trim()).filter(Boolean)

  const doImport = async (sources: { type: string; value: string }[], tagList: string[], onDuplicate: string) => {
    setImporting(true)
    try {
      const resp = await api.post('/documents/import', { sources, tags: tagList, on_duplicate: onDuplicate })
      if (resp.data.duplicates?.length > 0 && onDuplicate === 'ask') {
        setDuplicates(resp.data.duplicates)
        setPendingSources(sources)
        setPendingTags(tagList)
      } else {
        setUrl('')
        loadDocs()
      }
    } catch { /* ignore */ } finally { setImporting(false) }
  }

  const handleUrlImport = async () => {
    if (!url.trim()) return
    const sources = [{ type: 'url', value: url.trim() }]
    const tagList = parseTags(tags)
    await doImport(sources, tagList, 'ask')
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    form.append('tags', tags)
    setImporting(true)
    setUploadingFile(file.name)
    try {
      await api.post('/documents/upload', form)
      setTags('')
      loadDocs()
    } catch { /* ignore */ } finally {
      setImporting(false)
      setUploadingFile(null)
      e.target.value = ''
    }
  }

  const handleReImport = async () => {
    setDuplicates([])
    await doImport(pendingSources, pendingTags, 'overwrite')
  }

  const handleAbandon = () => {
    setDuplicates([])
    setPendingSources([])
    setPendingTags([])
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此文档？')) return
    await api.delete(`/documents/delete/${id}`)
    setDocs((prev) => prev.filter((d) => d.id !== id))
  }

  const handleRetry = async (id: string) => {
    setRetryingId(id)
    try {
      await api.post(`/documents/retry/${id}`)
    } catch { /* ignore */ } finally {
      setRetryingId(null)
      loadDocs()
    }
  }

  const formatLocalTime = (iso?: string): string => {
    if (!iso) return '—'
    const d = new Date(iso)
    if (isNaN(d.getTime())) return '—'
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">文档管理</h1>

      <div className="flex gap-3">
        <div className="flex-1 flex gap-2">
          <div className="flex-1 relative">
            <LinkIcon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="输入 URL 导入..."
              className="w-full pl-9 pr-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="标签（逗号分隔）"
            className="w-40 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            onClick={handleUrlImport}
            disabled={importing || !url.trim()}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
          >
            {importing ? <Loader2 size={14} className="animate-spin" /> : null}
            导入
          </button>
        </div>
        <input ref={fileRef} type="file" className="hidden" accept=".pdf,.md,.txt" onChange={handleFileUpload} />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={importing}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-sm font-medium rounded-lg transition-colors"
        >
          {importing ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          {importing && uploadingFile ? '上传中...' : '上传文件'}
        </button>
      </div>

      {uploadingFile && (
        <div className="flex items-center gap-3 px-4 py-3 bg-primary-900/30 border border-primary-700/40 rounded-lg text-sm text-primary-300">
          <Loader2 size={16} className="animate-spin shrink-0" />
          <span className="truncate">正在上传并处理：{uploadingFile}（文件较大时可能需要几分钟）</span>
        </div>
      )}

      {duplicates.length > 0 && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-full max-w-md space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">检测到重复文档</h2>
              <button onClick={handleAbandon} className="text-slate-400 hover:text-white"><X size={20} /></button>
            </div>
            <p className="text-sm text-slate-300">文档 URL 重复，是否强制导入？</p>
            {duplicates.map((dup) => (
              <div key={dup.source_id} className="bg-slate-900 rounded-lg p-3 text-sm">
                <p className="text-slate-300">{dup.existing_title}</p>
                <p className="text-xs text-slate-500 mt-1 truncate">{dup.source?.value || '—'}</p>
              </div>
            ))}
            <p className="text-sm text-slate-400">强制导入将删除旧文档并导入新内容。</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleAbandon}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-sm font-medium rounded-lg transition-colors"
              >
                否
              </button>
              <button
                onClick={handleReImport}
                disabled={importing}
                className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
              >
                是
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-slate-400">加载中...</div>
      ) : docs.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <FileText size={48} className="mx-auto mb-3 opacity-50" />
          <p>暂无文档</p>
          <p className="text-sm mt-1">导入 URL 或上传文件开始学习</p>
        </div>
      ) : (
        <div className="space-y-2">
          {docs.map((doc) => (
            <div key={doc.id} className="relative flex items-center gap-4 p-4 bg-slate-800 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors">
              <div className="absolute top-2.5 right-2.5 group">
                <button
                  className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg transition-colors cursor-default"
                  aria-label="文档操作"
                >
                  <MoreVertical size={16} />
                </button>
                {doc.status === 'failed' && doc.error_message && (
                  <div className="hidden group-hover:block absolute right-0 top-full mt-1 w-64 bg-slate-900 border border-slate-600 rounded-lg p-3 shadow-xl z-20">
                    <p className="text-xs text-red-400 font-medium mb-1">处理失败原因</p>
                    <p className="text-xs text-slate-300">{doc.error_message}</p>
                  </div>
                )}
              </div>
              <FileText size={20} className="text-primary-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate pr-6">{doc.title}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {doc.source_url || doc.source_type} &middot; {doc.chunk_count} 块 &middot; {formatLocalTime(doc.processed_at || doc.created_at)}
                </p>
                {doc.tags && doc.tags.length > 0 && (
                  <div className="flex gap-1 mt-1">
                    {doc.tags.map((tag) => (
                      <span key={tag} className="text-xs px-1.5 py-0.5 bg-slate-700 rounded text-slate-300">{tag}</span>
                    ))}
                  </div>
                )}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                doc.status === 'completed' ? 'bg-green-500/20 text-green-400'
                : doc.status === 'failed' ? 'bg-red-500/20 text-red-400'
                : 'bg-amber-500/20 text-amber-400'
              }`}>
                {doc.status === 'completed' ? '已完成' : doc.status === 'failed' ? '失败' : '处理中'}
              </span>
              {doc.status === 'failed' && (
                <button
                  onClick={() => handleRetry(doc.id)}
                  disabled={retryingId === doc.id}
                  className="px-2.5 py-1 text-xs bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-slate-200 rounded-lg transition-colors"
                >
                  {retryingId === doc.id ? '重试中...' : '重试'}
                </button>
              )}
              <button onClick={() => handleDelete(doc.id)} className="p-1.5 text-slate-400 hover:text-red-400 transition-colors">
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
