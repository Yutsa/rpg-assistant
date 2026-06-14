(ns rpg-assistant-web.views.shell
  (:require [rpg-assistant-web.router :as router]))

(defn- breadcrumb-view [location]
  (let [items (router/breadcrumbs location)]
    [:nav.breadcrumb {:aria-label "Fil d'Ariane"}
     (for [[index item] (map-indexed vector items)]
       [:span {:key (str (:label item) "-" index)}
        (when (pos? index) [:span {:aria-hidden true} " / "])
        (if-let [loc (:location item)]
          [:ui/a {:ui/location loc} (:label item)]
          [:strong (:label item)])])]))

(defn- sub-nav-view [location]
  (let [page-id (:location/page-id location)
        document-id (get-in location [:location/params :document-id])
        on-stat-blocks? (#{:pages/stat-blocks :pages/stat-block-detail} page-id)]
    (when document-id
      [:nav.sub-nav
       [:ui/a {:ui/location {:location/page-id :pages/document-explorer
                              :location/params {:document-id document-id}}
               :class (when-not on-stat-blocks? "active")}
        "Exploration"]
       [:ui/a {:ui/location {:location/page-id :pages/stat-blocks
                              :location/params {:document-id document-id}}
               :class (when on-stat-blocks? "active")}
        "Fiches stats"]])))

(defn shell-view [location body]
  [:div.app-shell
   [:header.app-header
    [:h1 "RPG Assistant"]
    (breadcrumb-view location)]
   (sub-nav-view location)
   body])
