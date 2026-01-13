import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";   // ✅ ADD
import Chatbot from "./pages/Chatbot";
import PrivateRoute from "./components/PrivateRoute";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />

        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />  {/* ✅ ADD */}

        <Route
          path="/chat"
          element={
            <PrivateRoute>
              <Chatbot />
            </PrivateRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
