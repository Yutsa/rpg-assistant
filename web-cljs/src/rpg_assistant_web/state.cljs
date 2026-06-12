(ns rpg-assistant-web.state
  (:require [rpg-assistant-web.routes :as routes]))

(defonce store
  (atom {:route (routes/parse-path (.-pathname js/location))
         :campaigns nil
         :campaigns-loading? false
         :campaigns-error nil}))

(defn initial-state []
  @store)

(defn reset-route! []
  (swap! store assoc :route (routes/parse-path (.-pathname js/location))))

(defn navigate! [path]
  (.pushState js/history nil "" path)
  (reset-route!))
