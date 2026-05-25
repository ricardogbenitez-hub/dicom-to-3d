import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const http = axios.create({ baseURL: BASE })

export const uploadDicoms = async (files, onProgress) => {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  const { data } = await http.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      // evt.loaded / evt.total gives real bytes transferred by the browser's XHR.
      // This reaches 100% once all bytes have left the client; the server still
      // needs a moment to write files to disk, so we cap at 99 here and let the
      // caller advance to 100 when the response arrives.
      if (evt.total && onProgress) {
        const pct = Math.min(Math.round((evt.loaded / evt.total) * 100), 99)
        onProgress(pct)
      }
    },
  })
  return data
}

export const createJob = async (params) => {
  const { data } = await http.post('/jobs', params)
  return data
}

export const getJob = async (id) => {
  const { data } = await http.get(`/jobs/${id}`)
  return data
}

export const downloadStl = async (id) => {
  const { data } = await http.get(`/jobs/${id}/download`, { responseType: 'blob' })
  return data
}

export const wsUrl = (id) =>
  `${BASE.replace(/^http/, 'ws')}/ws/jobs/${id}`
