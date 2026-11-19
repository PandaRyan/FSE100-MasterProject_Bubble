// src/pages/BubbleBlitzHard.tsx
// Hard mode page (Level 3): 120 seconds, plain tap bubbles + drag-to-spike & pinch bubbles, 3 strikes = lose.

import React from "react";
import BubbleBlitzBoard from "../components/BubbleBlitzBoard";
import { LEVEL_HARD } from "../api/bubbleApi";
import hardBannerImg from "../assets/bubbleblitzh.png";

// ---- Constants (with sources from backend hardbubbles.py) ----
const HARD_LEVEL_DURATION_SECONDS = 120; // Backend hardbubbles.py: LEVEL_DURATION = 120 s

const BubbleBlitzHard: React.FC = () => {
  return (
    <BubbleBlitzBoard
      level={LEVEL_HARD}
      modeTitle="HARD MODE"
      modeBannerImg={hardBannerImg}
      initialSeconds={HARD_LEVEL_DURATION_SECONDS}
    />
  );
};

export default BubbleBlitzHard;