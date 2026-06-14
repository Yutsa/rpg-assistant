(ns rpg-assistant-web.core
  (:require [replicant.alias :as alias]
            [replicant.dom :as r]
            [rpg-assistant-web.events :as events]
            [rpg-assistant-web.router :as router]
            [rpg-assistant-web.state :as state]
            [rpg-assistant-web.views :as views]))

(defn- render! []
  (r/render (js/document.getElementById "app")
            (views/render @state/store)
            {:alias-data {:routes router/routes}}))

(defn routing-anchor [attrs children]
  (let [routes (-> attrs :replicant/alias-data :routes)
        href (when-let [loc (:ui/location attrs)]
               (router/location->url routes loc))]
    (into [:a (cond-> attrs href (assoc :href href))]
          children)))

(defn- find-target-href [e]
  (some-> e .-target
          (.closest "a")
          (.getAttribute "href")))

(defn- route-click [e]
  (let [href (find-target-href e)]
    (when-let [location (router/url->location router/routes href)]
      (.preventDefault e)
      (let [current (router/current-location)
            replace? (router/essentially-same? location current)]
        (if replace?
          (.replaceState js/history nil "" href)
          (.pushState js/history nil "" href))
        (events/on-location-changed! location replace?)))))

(defn- on-popstate [_e]
  (events/on-location-changed! (router/current-location) false))

(defn- install-routing! []
  (js/document.body.addEventListener "click" route-click)
  (.addEventListener js/window "popstate" on-popstate))

(defonce routing-installed?
  (do
    (alias/register! :ui/a routing-anchor)
    (install-routing!)
    true))

(defn ^{:dev/after-load true :export true} reload! []
  (render!))

(defn ^:export init! []
  routing-installed?
  (events/set-render! render!)
  (r/set-dispatch! events/dispatch-event!)
  (events/on-location-changed! (router/current-location) false)
  (render!))
