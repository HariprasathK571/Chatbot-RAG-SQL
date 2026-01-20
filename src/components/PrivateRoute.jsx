import React from "react";
import { Navigate } from "react-router-dom";

export default function PrivateRoute({ children }) {
  const accessToken = localStorage.getItem("access_token");
  const refreshToken = localStorage.getItem("refresh_token");

  // ✅ allow if either exists (refresh will regenerate access)
  return accessToken || refreshToken ? children : <Navigate to="/login" replace />;
}
