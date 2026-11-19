// src/App.tsx
// Top-level router wiring Home, DigiBubble, Level Select, and all three Bubble Blitz modes.

import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { wakeServerHealth } from "./api/bubbleApi";
import Home from "./pages/Home";
import FingerCounting from "./pages/FingerCounting";
import BubbleBlitzLevelSelect from "./pages/BubbleBlitzLevelSelect";
import BubbleBlitzEasy from "./pages/BubbleBlitzEasy";
import BubbleBlitzMedium from "./pages/BubbleBlitzMedium";
import BubbleBlitzHard from "./pages/BubbleBlitzHard";

function App() {
  // Draft API Contract: call /health on app load to wake a sleeping free host before the child presses play
  useEffect(() => {
    void wakeServerHealth();
  }, []);

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/digibubble" element={<FingerCounting />} />
      <Route path="/bubbleblitzlevelselect" element={<BubbleBlitzLevelSelect />} />
      <Route path="/bubbleblitzeasy" element={<BubbleBlitzEasy />} />
      <Route path="/bubbleblitzmedium" element={<BubbleBlitzMedium />} />
      <Route path="/bubbleblitzhard" element={<BubbleBlitzHard />} />
    </Routes>
  );
}

export default App;