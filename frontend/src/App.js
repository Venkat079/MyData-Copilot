import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Navbar from "./components/Navbar";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import Files from "./pages/Files";
import FileDetail from "./pages/FileDetail";
import Settings from "./pages/Settings";
import PrivateRoute from "./components/PrivateRoute";
import { isAuthenticated } from "./utils/auth";

export default function App() {
  return (
    <div className="app-root">
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route
            path="/"
            element={
              isAuthenticated() ? (
                <Navigate to="/dashboard" />
              ) : (
                <Navigate to="/login" />
              )
            }
          />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <PrivateRoute>
                <Upload />
              </PrivateRoute>
            }
          />
          <Route
            path="/files"
            element={
              <PrivateRoute>
                <Files />
              </PrivateRoute>
            }
          />
          <Route
            path="/files/:id"
            element={
              <PrivateRoute>
                <FileDetail />
              </PrivateRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <PrivateRoute>
                <Settings />
              </PrivateRoute>
            }
          />

          <Route
            path="*"
            element={<div style={{ padding: 20 }}>Page not found</div>}
          />
        </Routes>
      </main>
    </div>
  );
}
