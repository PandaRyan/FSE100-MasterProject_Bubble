// src/pages/BubbleBlitzEasy.tsx
// Easy mode page (Level 1): 60 seconds, 1-tap bubbles, 3 strikes = lose.

import React from "react";
import BubbleBlitzBoard from "../components/BubbleBlitzBoard";
import { LEVEL_EASY } from "../api/bubbleApi";
import easyBannerImg from "../assets/bubbleblitze.png";

// ---- Constants (with sources from backend easybubble.py) ----
const EASY_LEVEL_DURATION_SECONDS = 60; // Backend easybubble.py: LEVEL_DURATION = 60 s

const BubbleBlitzEasy: React.FC = () => {
  return (
    <BubbleBlitzBoard
      level={LEVEL_EASY}
      modeTitle="EASY MODE"
      modeBannerImg={easyBannerImg}
      initialSeconds={EASY_LEVEL_DURATION_SECONDS}
    />
  );
};

export default BubbleBlitzEasy;