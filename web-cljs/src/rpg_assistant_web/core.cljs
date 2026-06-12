(ns rpg-assistant-web.core
  (:require [replicant.dom :as r]
            [rpg-assistant-web.events :as events]
            [rpg-assistant-web.state :as state]
            [rpg-assistant-web.views :as views]))

(defn- render! []
  (r/render (js/document.getElementById "app")
            (views/render @state/store)))

(defn ^{:dev/after-load true :export true} reload! []
  (render!))

(defn ^:export init! []
  (events/set-render! render!)
  (r/set-dispatch! events/dispatch-event!)
  (events/install-popstate!)
  (events/dispatch-event! nil [[:load-campaigns]])
  (render!))
