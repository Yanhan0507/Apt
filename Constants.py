import jinja2

__author__ = 'ChenguangLiu'

# DEPLOYMENT CONFIGURATIONS
SERVICE_URL = 'http://localhost:8080' #local
# SERVICE_URL = 'http://ee382v-apt-connexus.appspot.com/'
APP_ID = 'ee382v-apt-connexus'
MAILBOX_SURFIX = '.appspotmail.com'
REPORT_SENDER_NAME = 'trendingStreams'
# HTML_TEMPLATES FOLDER
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)



#   A FEW CONSTANT STRINGS USED ACROSS ALL THE SCRIPTS
KEYWORD_ERROR = 'error'
KEYWORD_STATUS = 'status'
KEYWORD_BLOBKEY = 'blob_key'


IDENTIFIER_CURRENT_USER = 'user'
IDENTIFIER_CURRENT_USER_ID = 'user_id'
IDENTIFIER_URL = 'url'
IDENTIFIER_JSON_MSG = 'application/json'
IDENTIFIER_STREAM_ID = 'stream_id'
IDENTIFIER_STREAM_NAME = 'stream_name'
IDENTIFIER_STREAM_DESC = 'stream_description'
IDENTIFIER_IMG_IDX_REQ_LIST = 'image_req_idx_lst'
IDENTIFIER_IMG_IDX_RES_LIST = 'image_res_idx_lst'
IDENTIFIER_BLOBKEY_LIST = 'blob_key_lst'
IDENTIFIER_IMAGEID_LIST = 'image_id_lst'
IDENTIFIER_IMAGEID = 'image_id'
IDENTIFIER_PHOTO_KEY = 'photo_key'
IDENTIFIER_STREAM_OWNER = 'stream_owner'
IDENTIFIER_COVER_URL = 'cover_url'

IDENTIFIER_GEO_VIEW = 'geo_view'

IDENTIFIER_SUBSCRIPTION_OPTION = 'subscribe_option'
IDENTIFIER_SUBSCRIPTION_URL = 'subscribe_url'
IDENTIFIER_CHECK_SUBSCRIPTION = 'check_subscription'

IDENTIFIER_UPLOAD_URL = 'upload_url'

IDENTIFIER_USER_STREAM_LIST = 'user_streams_list'
IDENTIFIER_USER_SUB_STREAM_LIST = 'user_sub_streams_list'

QUERY_BEGIN_DATE = 'query_begin_date'
QUERY_END_DATE = 'query_end_date'
KEYWORD_MARKER_LOC = 'location'
KEYWORD_MARKER_CONTENT = 'content'


NROF_IMGS_PER_PAGE = 3