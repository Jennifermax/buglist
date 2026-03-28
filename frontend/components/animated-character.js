'use client'
import { useState, useEffect, useRef } from 'react'

// 眼睛组件
export function AnimatedEyes({ isTyping, showPassword }) {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const eyesRef = useRef(null)

  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePos({ x: e.clientX, y: e.clientY })
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  const calculatePupilPosition = (eyeElement) => {
    if (!eyeElement) return { x: 0, y: 0 }

    const rect = eyeElement.getBoundingClientRect()
    const eyeCenterX = rect.left + rect.width / 2
    const eyeCenterY = rect.top + rect.height / 2

    const deltaX = mousePos.x - eyeCenterX
    const deltaY = mousePos.y - eyeCenterY
    const angle = Math.atan2(deltaY, deltaX)
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), 8)

    return {
      x: Math.cos(angle) * Math.min(distance, 8),
      y: Math.sin(angle) * Math.min(distance, 8)
    }
  }

  return (
    <div className="animated-character" ref={eyesRef}>
      <div className="character-face">
        {/* 左眼 */}
        <div className="eye left-eye">
          <div
            className="pupil"
            style={{
              transform: `translate(${calculatePupilPosition(eyesRef.current?.querySelector('.left-eye')).x}px, ${calculatePupilPosition(eyesRef.current?.querySelector('.left-eye')).y}px)`
            }}
          />
        </div>

        {/* 右眼 */}
        <div className="eye right-eye">
          <div
            className="pupil"
            style={{
              transform: `translate(${calculatePupilPosition(eyesRef.current?.querySelector('.right-eye')).x}px, ${calculatePupilPosition(eyesRef.current?.querySelector('.right-eye')).y}px)`
            }}
          />
        </div>

        {/* 嘴巴 - 根据状态改变 */}
        <div className={`mouth ${isTyping ? 'typing' : ''} ${showPassword ? 'surprised' : ''}`}>
          {showPassword && <span className="mouth-text">😮</span>}
        </div>
      </div>

      {/* 身体 */}
      <div className="character-body">
        <div className="body-shape"></div>
      </div>
    </div>
  )
}
