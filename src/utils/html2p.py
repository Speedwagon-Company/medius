from html2pic import Html2Pic

profileHtml = '''
    <div class="profile-card">
        <p class="profile-card-title">ROLE_PARAM</p>
        <img src="./users_pfp/IMGNAME" class="profile-card-pfp" alt="">
        <div class="profile-card-level"></div>
        <div class="profile-card-info">
            <div class="profile-card-info-item">
                <p>Sent:</p>
                <p> sent_param</p>
            </div>
            <div class="profile-card-info-item">
                <p>Recieved:</p>
                <p> recieved_param</p>
            </div>
        </div>
    </div>
'''

profileCss = '''
        *{
            padding: 0;
            margin: 0;
            font-family: Arial;
            color: white;
        }
        .profile-card{
            background-color: #151515;
            display: inline-flex;
            flex-direction: column;
            padding: 10px 20px;
            border-radius: 8px;
        }
        .profile-card-pfp{
            width: 300px;
            height: 300px;
            border-radius: 300px;
        }
        .profile-card-title {
            color: white;
            text-align: center;
            padding-bottom: 10px;
        }
        .profile-card-info {
            margin-top: 40px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-bottom: 20px;
        }
        .profile-card-info-item {
            background-color: #191919;
            display: flex;
            padding: 20px;
            justify-content: space-between;
            border-radius: 8px;SS
        }
'''

# TODO: add идемпотентность блять как это пишется правильно
def render_profile(pfp_name, member_id, path = ""):
    html = profileHtml + ""
    html = html.replace("IMGNAME", pfp_name)
    renderer = Html2Pic(html, profileCss)
    image = renderer.render()
    file_path = f"{path}{member_id}_profile.png"
    image.save(file_path)
    return file_path
