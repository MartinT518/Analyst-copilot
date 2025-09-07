import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import {
  Brain,
  Upload,
  Search,
  FileText,
  CheckCircle,
  Clock,
  AlertCircle,
  Download,
  Settings,
  Users,
  Database,
  Code,
  Zap,
  TrendingUp,
  Shield,
  Sparkles
} from 'lucide-react'
import './App.css'

// Main Dashboard Component
function Dashboard() {
  const [activeWorkflows, setActiveWorkflows] = useState([
    {
      id: 'wf_001',
      title: 'Customer Portal Requirements Analysis',
      status: 'in_progress',
      progress: 75,
      agent: 'Synthesizer',
      created: '2024-12-05T10:30:00Z',
      estimatedCompletion: '2024-12-05T14:00:00Z'
    },
    {
      id: 'wf_002',
      title: 'API Integration Task Breakdown',
      status: 'completed',
      progress: 100,
      agent: 'Taskmaster',
      created: '2024-12-05T09:15:00Z',
      estimatedCompletion: '2024-12-05T12:45:00Z'
    },
    {
      id: 'wf_003',
      title: 'Database Schema Verification',
      status: 'pending',
      progress: 0,
      agent: 'Verifier',
      created: '2024-12-05T11:00:00Z',
      estimatedCompletion: '2024-12-05T15:30:00Z'
    }
  ])

  const [systemStats, setSystemStats] = useState({
    totalDocuments: 12847,
    activeAgents: 4,
    completedWorkflows: 156,
    automationRate: 87
  })

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-green-500'
      case 'in_progress': return 'bg-blue-500'
      case 'pending': return 'bg-yellow-500'
      case 'failed': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircle className="w-4 h-4" />
      case 'in_progress': return <Clock className="w-4 h-4" />
      case 'pending': return <Clock className="w-4 h-4" />
      case 'failed': return <AlertCircle className="w-4 h-4" />
      default: return <Clock className="w-4 h-4" />
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <div className="relative">
                <Brain className="w-8 h-8 text-indigo-600" />
                <Sparkles className="w-4 h-4 text-yellow-500 absolute -top-1 -right-1" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Analyst Copilot</h1>
                <p className="text-xs text-gray-500">AI-Powered Analysis Automation</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                <Zap className="w-3 h-3 mr-1" />
                {systemStats.automationRate}% Automated
              </Badge>
              <Button variant="outline" size="sm">
                <Settings className="w-4 h-4 mr-2" />
                Settings
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total Documents</p>
                    <p className="text-2xl font-bold text-gray-900">{systemStats.totalDocuments.toLocaleString()}</p>
                  </div>
                  <Database className="w-8 h-8 text-blue-600" />
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Active Agents</p>
                    <p className="text-2xl font-bold text-gray-900">{systemStats.activeAgents}</p>
                  </div>
                  <Brain className="w-8 h-8 text-indigo-600" />
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Completed Workflows</p>
                    <p className="text-2xl font-bold text-gray-900">{systemStats.completedWorkflows}</p>
                  </div>
                  <CheckCircle className="w-8 h-8 text-green-600" />
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Automation Rate</p>
                    <p className="text-2xl font-bold text-gray-900">{systemStats.automationRate}%</p>
                  </div>
                  <TrendingUp className="w-8 h-8 text-purple-600" />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Active Workflows */}
          <div className="lg:col-span-2">
            <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Clock className="w-5 h-5 text-blue-600" />
                  <span>Active Workflows</span>
                </CardTitle>
                <CardDescription>
                  Real-time status of your analysis workflows
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <AnimatePresence>
                    {activeWorkflows.map((workflow, index) => (
                      <motion.div
                        key={workflow.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        transition={{ delay: index * 0.1 }}
                        className="p-4 rounded-lg border border-gray-200 bg-white/50 hover:bg-white/70 transition-all duration-200"
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-3">
                            <div className={`w-2 h-2 rounded-full ${getStatusColor(workflow.status)}`} />
                            <h3 className="font-medium text-gray-900">{workflow.title}</h3>
                          </div>
                          <Badge variant="outline" className="text-xs">
                            {workflow.agent}
                          </Badge>
                        </div>

                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-sm text-gray-600">
                            <span>Progress</span>
                            <span>{workflow.progress}%</span>
                          </div>
                          <Progress value={workflow.progress} className="h-2" />
                        </div>

                        <div className="flex items-center justify-between mt-3 text-xs text-gray-500">
                          <span>Started: {new Date(workflow.created).toLocaleTimeString()}</span>
                          <div className="flex items-center space-x-1">
                            {getStatusIcon(workflow.status)}
                            <span className="capitalize">{workflow.status.replace('_', ' ')}</span>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Quick Actions */}
          <div className="space-y-6">
            <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Zap className="w-5 h-5 text-yellow-600" />
                  <span>Quick Actions</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button className="w-full justify-start bg-indigo-600 hover:bg-indigo-700">
                  <Upload className="w-4 h-4 mr-2" />
                  Upload Documents
                </Button>
                <Button variant="outline" className="w-full justify-start">
                  <Search className="w-4 h-4 mr-2" />
                  Search Knowledge Base
                </Button>
                <Button variant="outline" className="w-full justify-start">
                  <FileText className="w-4 h-4 mr-2" />
                  New Analysis Request
                </Button>
                <Button variant="outline" className="w-full justify-start">
                  <Download className="w-4 h-4 mr-2" />
                  Export Results
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Shield className="w-5 h-5 text-green-600" />
                  <span>System Health</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Ingest Service</span>
                    <Badge className="bg-green-100 text-green-800">Healthy</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Agent Orchestrator</span>
                    <Badge className="bg-green-100 text-green-800">Healthy</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Vector Database</span>
                    <Badge className="bg-green-100 text-green-800">Healthy</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Code Analyzer</span>
                    <Badge className="bg-green-100 text-green-800">Healthy</Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}

// Upload Component
function UploadPage() {
  const [dragActive, setDragActive] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState([])

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const files = Array.from(e.dataTransfer.files)
      setUploadedFiles(prev => [...prev, ...files.map(file => ({
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'uploading'
      }))])

      // Simulate upload progress
      setTimeout(() => {
        setUploadedFiles(prev => prev.map(f => ({ ...f, status: 'completed' })))
      }, 2000)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Document Upload</h1>
          <p className="text-gray-600">Upload documents to expand your knowledge base</p>
        </div>

        <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg mb-8">
          <CardContent className="p-8">
            <div
              className={`border-2 border-dashed rounded-lg p-12 text-center transition-all duration-200 ${
                dragActive
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Drop files here or click to upload
              </h3>
              <p className="text-gray-500 mb-4">
                Supports PDF, DOCX, TXT, MD, CSV, and code files
              </p>
              <Button className="bg-indigo-600 hover:bg-indigo-700">
                Choose Files
              </Button>
            </div>
          </CardContent>
        </Card>

        {uploadedFiles.length > 0 && (
          <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg">
            <CardHeader>
              <CardTitle>Uploaded Files</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {uploadedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-white/50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <FileText className="w-5 h-5 text-blue-600" />
                      <div>
                        <p className="font-medium text-gray-900">{file.name}</p>
                        <p className="text-sm text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                      </div>
                    </div>
                    <Badge className={file.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'}>
                      {file.status === 'completed' ? 'Processed' : 'Processing...'}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

// Search Component
function SearchPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)

  const handleSearch = async () => {
    if (!searchQuery.trim()) return

    setIsSearching(true)
    // Simulate search
    setTimeout(() => {
      setSearchResults([
        {
          id: 1,
          title: "Customer Authentication Requirements",
          excerpt: "The system shall provide secure authentication mechanisms including multi-factor authentication for enhanced security...",
          source: "requirements_doc.pdf",
          relevance: 0.95,
          type: "document"
        },
        {
          id: 2,
          title: "User Management API Endpoints",
          excerpt: "class UserController { public function authenticate($credentials) { // Implementation for user authentication...",
          source: "UserController.php",
          relevance: 0.87,
          type: "code"
        },
        {
          id: 3,
          title: "Database Schema - Users Table",
          excerpt: "CREATE TABLE users ( id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, password_hash VARCHAR(255)...",
          source: "schema.sql",
          relevance: 0.82,
          type: "schema"
        }
      ])
      setIsSearching(false)
    }, 1500)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Knowledge Search</h1>
          <p className="text-gray-600">Search across documents, code, and database schemas</p>
        </div>

        <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg mb-8">
          <CardContent className="p-6">
            <div className="flex space-x-4">
              <div className="flex-1">
                <input
                  type="text"
                  placeholder="Search for requirements, code, or database schemas..."
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                />
              </div>
              <Button
                onClick={handleSearch}
                disabled={isSearching}
                className="bg-indigo-600 hover:bg-indigo-700"
              >
                <Search className="w-4 h-4 mr-2" />
                {isSearching ? 'Searching...' : 'Search'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {searchResults.length > 0 && (
          <div className="space-y-4">
            {searchResults.map((result) => (
              <motion.div
                key={result.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: result.id * 0.1 }}
              >
                <Card className="bg-white/60 backdrop-blur-sm border-0 shadow-lg hover:shadow-xl transition-shadow">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="text-lg font-semibold text-gray-900">{result.title}</h3>
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline" className="text-xs">
                          {result.type}
                        </Badge>
                        <Badge className="bg-green-100 text-green-800 text-xs">
                          {Math.round(result.relevance * 100)}% match
                        </Badge>
                      </div>
                    </div>
                    <p className="text-gray-600 mb-3">{result.excerpt}</p>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">Source: {result.source}</span>
                      <Button variant="outline" size="sm">
                        View Details
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Main App Component
function App() {
  return (
    <Router>
      <div className="min-h-screen">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
