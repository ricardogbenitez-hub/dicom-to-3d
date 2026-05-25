import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const http = axios.create({ baseURL: BASE })

export const uploadDicoms = async (files) => {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  const { data } = await http.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
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
