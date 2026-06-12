(ns rpg-assistant.web.components.common
  (:require [uix.core :refer [defui $]]))

(defui loading-state
  [{:keys [label]}]
  ($ :div.state-box {:role "status"}
    ($ :div.spinner)
    ($ :p.muted (or label "Chargement…"))))

(defui error-state
  [{:keys [message on-retry]}]
  ($ :div.state-box.error
    ($ :p message)
    (when on-retry
      ($ :button.btn {:type "button" :on-click on-retry} "Réessayer"))))

(defui empty-state
  [{:keys [title message children]}]
  ($ :div.state-box
    ($ :h2 title)
    (when message ($ :p.muted message))
    children))
