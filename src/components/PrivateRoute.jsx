import React from "react";
import { Navigate } from "react-router-dom";

export default function PrivateRoute({ children }) {
  const accessToken = localStorage.getItem("access_token");
  const refreshToken = localStorage.getItem("refresh_token");

  // ✅ allow app access if refresh token exists too
  // because access token can be refreshed automatically.
  return accessToken || refreshToken ? children : <Navigate to="/login" replace />;
}
