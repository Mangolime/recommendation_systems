import pandas as pd
import numpy as np

# Для работы с матрицами
from scipy.sparse import csr_matrix

# Матричная факторизация
from implicit.als import AlternatingLeastSquares
from implicit.nearest_neighbours import ItemItemRecommender  # нужен для одного трюка
from implicit.nearest_neighbours import bm25_weight, tfidf_weight


class MainRecommender:
    # Рекомендации, которые можно получить из ALS
    
    def __init__(self, data, weighting=True):
        
        # your_code. Это не обязательная часть. Но если вам удобно что-либо посчитать тут - можно это сделать
        self.data = data
        self.user_item_matrix = self.prepare_matrix(data)  # pd.DataFrame
        self.id_to_itemid, self.id_to_userid, self.itemid_to_id, self.userid_to_id = self.prepare_dicts(self.user_item_matrix)
        
        if weighting:
            self.user_item_matrix = bm25_weight(self.user_item_matrix.T).T 
        
        self.model = self.fit(self.user_item_matrix)
        self.own_recommender = self.fit_own_recommender(self.user_item_matrix)
     
    @staticmethod
    def prepare_matrix(data):
        user_item_matrix = pd.pivot_table(data, 
                                  index='user_id', columns='item_id', 
                                  values='quantity', # Можно пробовать другие варианты
                                  aggfunc='count', 
                                  fill_value=0
                                 )

        user_item_matrix = user_item_matrix.astype(float) # необходимый тип матрицы для implicit
        return user_item_matrix
    
    @staticmethod
    def prepare_dicts(user_item_matrix):
        # Подготавливает вспомогательные словари
        
        userids = user_item_matrix.index.values
        itemids = user_item_matrix.columns.values

        matrix_userids = np.arange(len(userids))
        matrix_itemids = np.arange(len(itemids))

        id_to_itemid = dict(zip(matrix_itemids, itemids))
        id_to_userid = dict(zip(matrix_userids, userids))

        itemid_to_id = dict(zip(itemids, matrix_itemids))
        userid_to_id = dict(zip(userids, matrix_userids))
        
        return id_to_itemid, id_to_userid, itemid_to_id, userid_to_id
     
    @staticmethod
    def fit_own_recommender(user_item_matrix):
        # Обучает модель, которая рекомендует товары, среди товаров, купленных юзером
    
        own_recommender = ItemItemRecommender(K=1, num_threads=4)
        own_recommender.fit(csr_matrix(user_item_matrix).T.tocsr())
        
        return own_recommender
    
    @staticmethod
    def fit(user_item_matrix, n_factors=20, regularization=0.001, iterations=15, num_threads=4):
        # Обучает ALS
        
        model = AlternatingLeastSquares(factors=n_factors, 
                                             regularization=regularization,
                                             iterations=iterations,  
                                             num_threads=num_threads)
        model.fit(csr_matrix(user_item_matrix).T.tocsr())
        
        return model

    def get_similar_items_recommendation(self, user, N=5):
        # Рекомендуем товары, похожие на топ-N купленных юзером товаров

        # your_code
        # Найдем топ-N товаров среди купленных пользователем
        popularity = self.data.query('user_id == @user').groupby(['item_id'])['quantity'].count().reset_index()
        popularity.sort_values('quantity', ascending=False, inplace=True)
        
        popularity = popularity[popularity['item_id'] != 999999]
        popularity.sort_values('quantity', ascending=False, inplace=True)
        popularity = popularity.head(5)
               
        # Для каждого из найденных товаров найдем по одному похожему
        res = []
        for x in popularity['item_id']:
            recs = self.model.similar_items(self.itemid_to_id[x], N=2)
            res.append(self.id_to_itemid[recs[1][0]])
#        assert len(res) == N, 'Количество рекомендаций != {}'.format(N)
        return res
    
    def get_similar_users_recommendation(self, user, N=5):
    # Рекомендуем топ-N товаров, среди купленных похожими юзерами
    
        # your_code
        # Найдем N похожих пользователя
        similar_users = [self.id_to_userid[i] for i, v in self.model.similar_users(self.userid_to_id[user], N=6)[1:]]
        
        # Среди товаров, купленных похожими пользователями, отберем топ-N
        popularity = self.data.query('user_id in @similar_users').groupby(['user_id', 'item_id'])['quantity'].count().reset_index()
        popularity.sort_values('quantity', ascending=False, inplace=True)
        popularity = popularity[popularity['item_id'] != 999999]
        popularity = popularity.groupby('user_id').head(5).reset_index()
        candidates = popularity.groupby('item_id', as_index=False)['quantity'].sum().sort_values('quantity', ascending=False)
        res = candidates.head(N)['item_id'].values
                      
        #assert len(res) == N, 'Количество рекомендаций != {}'.format(N)
        return res