import sys
import os
from html2pic import Html2Pic


html = '''
    <div class="profile-card">
        <p class="profile-card-title">ROLE_PARAM</p>
        <img src="./avatar.webp" class="profile-card-pfp" alt="">
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

css = '''
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
            border-radius: 8px;
        }
'''

a = "aba"
b = a + ""
a = "huis"
print(b, a)
# renderer = Html2Pic(html, css)
# image = renderer.render()
# image.save("01_quick_start_output.png")

# print("Quick start example rendered successfully!")
# print("Output saved to '01_quick_start_output.png'")