import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import backgroundVideo from "../assets/backgroundvideo.mp4";
import back from "../assets/back.png";
import bubbleImg from "../assets/bubble.png";
import sharkImg from "../assets/shark.png";
import "../fingercounting.css";

type GameStatus = "playing" | "won" | "lost";

const shuffleTargets = (): number[] => {
    const nums = [1, 2, 3, 4, 5];
    for (let i = nums.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [nums[i], nums[j]] = [nums[j], nums[i]];
    }
    return nums;
};

const FingerCounting: React.FC = () => {
    const navigate = useNavigate();

    const [videoSrc, setVideoSrc] = useState<string | null>(null);
    const [currentPrediction, setCurrentPrediction] = useState<number | null>(null);

    // Game State
    const [targets, setTargets] = useState<number[]>(() => shuffleTargets());
    const [currentIndex, setCurrentIndex] = useState<number>(0);
    const [timeLeft, setTimeLeft] = useState<number>(60);
    const [gameStatus, setGameStatus] = useState<GameStatus>("playing");
    const [progress, setProgress] = useState<number>(0);
    const [isSharkHit, setIsSharkHit] = useState<boolean>(false);

    const holdTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const timeHeldRef = useRef<number>(0);
    const wsRef = useRef<WebSocket | null>(null);

    const targetNumber = targets[currentIndex];
    // Each successful hold removes 20% of the shark's health
    const sharkHealth = gameStatus === "won" ? 0 : ((targets.length - currentIndex) / targets.length) * 100;

    const startNewGame = () => {
        if (holdTimerRef.current) {
            clearInterval(holdTimerRef.current);
            holdTimerRef.current = null;
        }
        setTargets(shuffleTargets());
        setCurrentIndex(0);
        setTimeLeft(60);
        setGameStatus("playing");
        setProgress(0);
        setIsSharkHit(false);
        timeHeldRef.current = 0;
    };

    // WebSocket Connection
    useEffect(() => {
        const ws = new WebSocket("ws://localhost:8000/ws/video");
        wsRef.current = ws;

        ws.onopen = () => console.log("Connected to FastAPI WebSocket");
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setVideoSrc(`data:image/jpeg;base64,${data.image}`);
            setCurrentPrediction(data.prediction);
        };
        ws.onerror = (error) => console.error("WebSocket Error:", error);

        return () => {
            wsRef.current?.close();
        };
    }, []);

    // 60-Second Game Countdown
    useEffect(() => {
        if (gameStatus !== "playing") return;

        const countdown = setInterval(() => {
            setTimeLeft((prev) => {
                if (prev <= 1) {
                    setGameStatus("lost");
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(countdown);
    }, [gameStatus]);

    // Finger Hold Detection Logic
    useEffect(() => {
        if (gameStatus !== "playing") return;

        if (currentPrediction === targetNumber) {
            if (!holdTimerRef.current) {
                holdTimerRef.current = setInterval(() => {
                    timeHeldRef.current += 100;
                    setProgress((timeHeldRef.current / 1500) * 100);

                    if (timeHeldRef.current >= 1500) {
                        clearInterval(holdTimerRef.current!);
                        holdTimerRef.current = null;
                        timeHeldRef.current = 0;
                        setProgress(0);

                        // Trigger brief hit animation on the shark
                        setIsSharkHit(true);
                        setTimeout(() => setIsSharkHit(false), 300);

                        // Advance to next target or win
                        if (currentIndex + 1 >= targets.length) {
                            setGameStatus("won");
                        } else {
                            setCurrentIndex((prev) => prev + 1);
                        }
                    }
                }, 100);
            }
        } else {
            if (holdTimerRef.current) {
                clearInterval(holdTimerRef.current);
                holdTimerRef.current = null;
            }
            timeHeldRef.current = 0;
            setProgress(0);
        }

        return () => {
            if (holdTimerRef.current) {
                clearInterval(holdTimerRef.current);
                holdTimerRef.current = null;
            }
        };
    }, [currentPrediction, targetNumber, currentIndex, targets.length, gameStatus]);

    return (
        <div className="home-screen">
            <button className="back-button" onClick={() => navigate("/")}>
                <img src={back} alt="Back" className="back-icon" />
            </button>

            <video
                className="background-video"
                src={backgroundVideo}
                autoPlay
                loop
                muted
                playsInline
            />

            <div className="game-container">
                {/* Top HUD: Timer & Shark Boss */}
                <div className="boss-hud">
                    <div className={`timer-badge ${timeLeft <= 10 ? "urgent" : ""}`}>
                        ⏱ {timeLeft}s
                    </div>

                    <div className="shark-section">
                        <img
                            src={sharkImg}
                            alt="Shark Boss"
                            className={`shark-img ${isSharkHit ? "shark-hit" : ""} ${
                                gameStatus === "lost" ? "shark-swim-away" : ""
                            }`}
                        />
                        <div className="health-bar-bg">
                            <div
                                className="health-bar-fill"
                                style={{ width: `${sharkHealth}%` }}
                            />
                        </div>
                    </div>
                </div>

                {/* Target Prompt & Hold Bubbles */}
                <div className="game-header">
                    <h2>
                        Hold up <span>{targetNumber}</span> {targetNumber === 1 ? "finger" : "fingers"}!
                    </h2>

                    <div className="bubbles-container">
                        {[1, 2, 3, 4, 5].map((bubbleIndex) => {
                            const isActive = progress > (bubbleIndex - 1) * 20;
                            return (
                                <img
                                    key={bubbleIndex}
                                    src={bubbleImg}
                                    alt="progress bubble"
                                    className={`progress-bubble ${isActive ? "active" : "inactive"}`}
                                />
                            );
                        })}
                    </div>
                </div>

                {/* Webcam Feed */}
                <div className="video-frame">
                    {videoSrc ? (
                        <img src={videoSrc} alt="Webcam feed" />
                    ) : (
                        <p>Loading Camera Model...</p>
                    )}
                </div>

                {/* Win / Lose Overlay */}
                {gameStatus !== "playing" && (
                    <div className={`win-overlay ${gameStatus}`}>
                        <h1>{gameStatus === "won" ? "You Defeated the Shark!" : "Time's Up!"}</h1>
                        <p>
                            {gameStatus === "won"
                                ? `Finished with ${timeLeft} seconds left.`
                                : "The shark got away. Try again!"}
                        </p>
                        <button onClick={startNewGame}>Play Again</button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default FingerCounting;