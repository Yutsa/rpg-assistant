(ns rpg-assistant.web.components.app-shell
  (:require ["react-router-dom" :refer [Link Outlet useLocation]]
            [uix.core :refer [defui $]]))

(defn- crumbs-from-path [pathname]
  (let [parts (vec (remove empty? (.split pathname "/")))
        items (atom [{:label "Campagnes" :to "/"}])]
    (when (and (= (first parts) "campaigns") (second parts))
      (swap! items conj {:label (second parts) :to (str "/campaigns/" (second parts))}))
    (when (and (= (first parts) "documents") (second parts))
      (let [doc-id (second parts)]
        (swap! items conj {:label doc-id :to (str "/documents/" doc-id)})
        (when (= (nth parts 2 nil) "stat-blocks")
          (swap! items conj {:label "Fiches stats"
                             :to (str "/documents/" doc-id "/stat-blocks")})
          (when-let [name (nth parts 3 nil)]
            (swap! items conj {:label (js/decodeURIComponent name)})))
        (when (and (= (nth parts 2 nil) "chunks") (nth parts 3 nil))
          (swap! items conj {:label (str "Chunk " (nth parts 3))}))))
    @items))

(defui app-shell []
  (let [location (useLocation)
        pathname (.-pathname location)
        crumbs (crumbs-from-path pathname)
        document-match (.match pathname #"^/documents/([^/]+)")
        document-id (when document-match (aget document-match 1))
        on-stat-blocks? (.includes pathname "/stat-blocks")]
    ($ :div.app-shell
      ($ :header.app-header
        ($ :h1 "RPG Assistant")
        ($ :nav.breadcrumb {:aria-label "Fil d'Ariane"}
          (for [[idx item] (map-indexed vector crumbs)]
            ($ :span {:key (str (:label item) "-" idx)}
              (when (pos? idx) ($ :span {:aria-hidden true} " / "))
              (if (:to item)
                ($ Link {:to (:to item)} (:label item))
                ($ :strong (:label item)))))))
      (when document-id
        ($ :nav.sub-nav
          ($ Link {:to (str "/documents/" document-id)
                   :class (when (and (not on-stat-blocks?)
                                     (= pathname (str "/documents/" document-id)))
                            "active")}
            "Exploration")
          ($ Link {:to (str "/documents/" document-id "/stat-blocks")
                   :class (when on-stat-blocks? "active")}
            "Fiches stats")))
      ($ Outlet))))
