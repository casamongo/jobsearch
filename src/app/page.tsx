"use client";

import { useState } from "react";

interface Job {
  company: string;
  stage: string;
  title: string;
  url: string;
  location: string;
  compensation: string;
  datePosted: string;
  source: string;
  isNew: boolean;
}

interface DebugInfo {
  stopReason: string;
  blockTypes: string[];
  textLength: number;
  rawPreview: string;
}

export default function Home() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [debug, setDebug] = useState<DebugInfo | null>(null);

  async function handleSearch() {
    setLoading(true);
    setError(null);
    setJobs([]);
    setDebug(null);

    try {
      const res = await fetch("/api/search", { method: "POST" });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Search failed");
      }

      setJobs(data.jobs || []);
      setDebug(data.debug || null);
      setSearched(true);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">
              WealthTech Job Search
            </h1>
            <p className="text-sm text-slate-500">
              AI-powered GTM & leadership role discovery
            </p>
          </div>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium px-5 py-2.5 rounded-lg transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin h-4 w-4"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Searching...
              </>
            ) : (
              <>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z"
                    clipRule="evenodd"
                  />
                </svg>
                Search Now
              </>
            )}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Loading State */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="relative">
              <div className="h-16 w-16 rounded-full border-4 border-slate-200 border-t-blue-600 animate-spin" />
            </div>
            <p className="mt-6 text-slate-600 font-medium">
              Searching for wealthtech leadership roles...
            </p>
            <p className="mt-2 text-sm text-slate-400">
              This may take a minute as we search across multiple sources
            </p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-2">
              <svg
                className="h-5 w-5 text-red-500"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <p className="text-red-800 font-medium">Search Error</p>
            </div>
            <p className="mt-1 text-red-700 text-sm">{error}</p>
          </div>
        )}

        {/* Empty State */}
        {!loading && !searched && !error && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="bg-blue-100 rounded-full p-4 mb-4">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-8 w-8 text-blue-600"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-slate-900">
              Ready to Search
            </h2>
            <p className="mt-2 text-slate-500 max-w-md">
              Click &quot;Search Now&quot; to find current GTM and commercial
              leadership roles at wealthtech companies across the US.
            </p>
          </div>
        )}

        {/* Results Table */}
        {!loading && jobs.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">
                Search Results
              </h2>
              <span className="text-sm text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
                {jobs.length} role{jobs.length !== 1 ? "s" : ""} found
              </span>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200">
                      <th className="text-left px-4 py-3 font-semibold text-slate-600 whitespace-nowrap">
                        #
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-600 whitespace-nowrap">
                        Company
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-600 whitespace-nowrap">
                        Stage
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-600 whitespace-nowrap">
                        Role / Title
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-600 whitespace-nowrap">
                        Location
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-600 whitespace-nowrap">
                        Compensation
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-600 whitespace-nowrap">
                        Date Posted
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-600 whitespace-nowrap">
                        Source
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {jobs.map((job, index) => (
                      <tr
                        key={index}
                        className="hover:bg-blue-50/50 transition-colors"
                      >
                        <td className="px-4 py-3 text-slate-400 font-mono">
                          {index + 1}
                        </td>
                        <td className="px-4 py-3 font-medium text-slate-900 whitespace-nowrap">
                          {job.company}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                            {job.stage}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {job.url ? (
                              <a
                                href={job.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                              >
                                {job.title}
                              </a>
                            ) : (
                              <span className="font-medium">{job.title}</span>
                            )}
                            {job.isNew && (
                              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-700 uppercase tracking-wide">
                                New
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-slate-600 whitespace-nowrap">
                          {job.location}
                        </td>
                        <td className="px-4 py-3 text-slate-600 whitespace-nowrap">
                          {job.compensation}
                        </td>
                        <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                          {job.datePosted}
                        </td>
                        <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                          {job.source}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* No results after search */}
        {!loading && searched && jobs.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="bg-amber-100 rounded-full p-4 mb-4">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-8 w-8 text-amber-600"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-slate-900">
              No Results Parsed
            </h2>
            <p className="mt-2 text-slate-500 max-w-md">
              The search completed but no roles could be extracted. See debug
              info below.
            </p>
            {debug && (
              <div className="mt-6 w-full max-w-2xl text-left bg-white border border-slate-200 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-2">
                  Debug Info
                </h3>
                <dl className="text-xs text-slate-600 space-y-1">
                  <div>
                    <dt className="font-medium inline">Stop Reason:</dt>{" "}
                    <dd className="inline">{debug.stopReason}</dd>
                  </div>
                  <div>
                    <dt className="font-medium inline">Content Blocks:</dt>{" "}
                    <dd className="inline">{debug.blockTypes.join(", ")}</dd>
                  </div>
                  <div>
                    <dt className="font-medium inline">Text Length:</dt>{" "}
                    <dd className="inline">{debug.textLength} chars</dd>
                  </div>
                </dl>
                {debug.rawPreview && (
                  <pre className="mt-3 p-3 bg-slate-50 rounded text-xs text-slate-700 overflow-x-auto whitespace-pre-wrap break-words max-h-64 overflow-y-auto">
                    {debug.rawPreview}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
